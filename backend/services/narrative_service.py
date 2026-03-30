"""Service C: Evidence Narrative Generator for SAIA V4."""

import logging
import json
import asyncpg
from uuid import UUID

from .llm_client import LLMClient
from .rag_service import RAGService
from .websocket import get_connection_manager

logger = logging.getLogger(__name__)


async def generate_narrative(
    db: asyncpg.Connection,
    case_id: UUID,
    user_role: str,
    data_scope: list[str],
    llm_client: LLMClient,
    rag_service: RAGService,
) -> None:
    """
    Background task to generate evidence narrative for a case.

    Steps:
    1. Set narrative_status = 'generating'
    2. Load case + all alerts + log events
    3. Query Qdrant for all cited NCA controls
    4. Assemble prompt
    5. Call LLM (non-streaming, max_tokens=4000)
    6. Save narrative_draft
    7. Set narrative_status = 'ready'
    8. Push WebSocket notification

    Args:
        db: AsyncPG connection
        case_id: Case ID
        user_role: User's role (for prompt context)
        data_scope: User's data scope
        llm_client: LLM client
        rag_service: RAG service
    """
    try:
        # Set generating status
        await db.execute("""
            UPDATE cases
            SET narrative_status = 'generating', updated_at = NOW()
            WHERE id = $1
        """, case_id)

        # Load case
        case = await db.fetchrow("""
            SELECT id, case_number, title, description, status, severity, created_at
            FROM cases
            WHERE id = $1
        """, case_id)

        if not case:
            logger.warning(f"Case {case_id} not found")
            return

        # Load all alerts for this case
        alerts = await db.fetch("""
            SELECT id, alert_number, domain, severity, anomaly_score,
                   top_features, llm_assessment, analyst_comment, analyst_verdict,
                   created_at, event_ids
            FROM alerts
            WHERE case_id = $1
            ORDER BY created_at ASC
        """, case_id)

        if not alerts:
            logger.warning(f"No alerts found for case {case_id}")
            return

        # Collect all event IDs and load events
        all_event_ids = []
        for alert in alerts:
            event_ids = alert.get("event_ids") or []
            all_event_ids.extend(event_ids)

        events = []
        if all_event_ids:
            events = await db.fetch("""
                SELECT id, timestamp, event_type, action, principal, resource, result,
                       source_ip, domain
                FROM log_events
                WHERE id = ANY($1)
                ORDER BY timestamp ASC
            """, all_event_ids)

        # Collect all control IDs from alerts and query Qdrant
        control_ids_set = set()
        for alert in alerts:
            assessment = alert.get("llm_assessment")
            if assessment:
                try:
                    if isinstance(assessment, str):
                        assessment = json.loads(assessment)
                    control_ids_set.add(assessment.get("primary_clause"))
                    control_ids_set.extend(assessment.get("secondary_clauses", []))
                except (json.JSONDecodeError, TypeError):
                    pass

        control_ids = list(filter(None, control_ids_set))
        qdrant_controls = []
        if control_ids:
            qdrant_controls = await rag_service.get_controls_by_ids(control_ids)

        # Build controls reference text
        controls_text = ""
        for control in qdrant_controls:
            payload = control.get("payload", {})
            control_id = payload.get("control_id", "unknown")
            title = payload.get("title", "")
            text = payload.get("text", "")
            controls_text += f"\n{control_id}: {title}\n{text}\n"

        # Build alert summary for prompt
        alerts_summary = ""
        for alert in alerts:
            alerts_summary += f"\n### Alert {alert['alert_number']}\n"
            alerts_summary += f"- Domain: {alert['domain']}\n"
            alerts_summary += f"- Severity: {alert['severity']}\n"
            alerts_summary += f"- Detected: {alert['created_at']}\n"
            alerts_summary += f"- Verdict: {alert['analyst_verdict'] or 'Pending'}\n"
            
            if alert.get("llm_assessment"):
                try:
                    assessment = alert["llm_assessment"]
                    if isinstance(assessment, str):
                        assessment = json.loads(assessment)
                    alerts_summary += f"- Primary Clause: {assessment.get('primary_clause', 'N/A')}\n"
                    alerts_summary += f"- Confidence: {assessment.get('confidence', 'N/A')}\n"
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if alert.get("analyst_comment"):
                alerts_summary += f"- Comment: {alert['analyst_comment']}\n"

        # Build events timeline
        events_timeline = ""
        for event in events[:20]:  # Limit to first 20 events
            events_timeline += f"\n- {event['timestamp']}: {event['event_type']} - {event['action']} on {event['resource']} (result: {event['result']})\n"

        # Assemble system prompt
        system_prompt = f"""You are a cybersecurity compliance report writer. Generate a structured evidence narrative for a resolved security case. The narrative must be suitable for inclusion in a regulatory compliance evidence pack submitted to Saudi NCA auditors.

Structure your response as:
1. **Executive Summary** (2-3 sentences)
2. **Timeline of Events** (chronological, with timestamps)
3. **Regulatory Context** (which ECC controls are implicated and why)
4. **Evidence Description** (what the logs show, citing specific events)
5. **Detection & Analysis** (how the violation was detected: rule-based, AI-based, or both)
6. **Resolution** (what actions were taken, by whom, when)
7. **Recommendations** (preventive measures)

Rules:
- Use formal, professional language suitable for regulatory submission.
- Cite specific ECC control IDs.
- Reference specific event timestamps and alert IDs.
- Do not fabricate any details not present in the provided context.

Current user role: {user_role}
Data scope: {", ".join(data_scope)}
"""

        # Assemble user prompt
        user_prompt = f"""## Case Information
Case Number: {case['case_number']}
Title: {case['title']}
Description: {case['description'] or 'N/A'}
Status: {case['status']}
Severity: {case['severity']}
Created: {case['created_at']}

## Relevant NCA ECC Controls
{controls_text if controls_text else "No controls referenced."}

## Alerts in This Case
{alerts_summary}

## Timeline of Events
{events_timeline if events_timeline else "No events available."}

## Instructions
Generate a comprehensive evidence narrative suitable for regulatory submission. Use the above information to structure a professional compliance report."""

        # Call LLM
        narrative_text = await llm_client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4000,
            temperature=0.1,
        )

        # Save narrative draft
        await db.execute("""
            UPDATE cases
            SET narrative_draft = $1, narrative_status = 'ready',
                narrative_approved = FALSE, updated_at = NOW()
            WHERE id = $2
        """, narrative_text, case_id)

        logger.info(f"Generated narrative for case {case_id}")

        # Push WebSocket notification
        ws_manager = get_connection_manager()
        await ws_manager.broadcast({
            "type": "narrative_ready",
            "case_id": str(case_id),
            "case_number": case["case_number"],
        })

    except Exception as e:
        logger.error(f"Error generating narrative for case {case_id}: {e}")
        # Mark as failed
        try:
            await db.execute("""
                UPDATE cases
                SET narrative_status = 'failed', updated_at = NOW()
                WHERE id = $1
            """, case_id)
        except Exception as inner_e:
            logger.error(f"Error updating case status: {inner_e}")


async def approve_narrative(
    db: asyncpg.Connection,
    case_id: UUID,
    user_id: UUID,
) -> None:
    """
    Mark narrative as approved.

    Args:
        db: AsyncPG connection
        case_id: Case ID
        user_id: User ID (approver)
    """
    try:
        await db.execute("""
            UPDATE cases
            SET narrative_approved = TRUE,
                narrative_approved_by = $1,
                narrative_approved_at = NOW(),
                updated_at = NOW()
            WHERE id = $2
        """, user_id, case_id)

        logger.info(f"Approved narrative for case {case_id}")

    except Exception as e:
        logger.error(f"Error approving narrative: {e}")
        raise
