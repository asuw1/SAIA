"""Service A: Anomaly Enrichment for SAIA V4."""

import logging
import json
import asyncpg
from typing import Optional
from uuid import UUID

from .llm_client import LLMClient
from .rag_service import RAGService

logger = logging.getLogger(__name__)

# Generate valid ECC clause IDs: 2-X-Y where X is 1-14, Y varies per domain
# For simplicity, we'll create ~110 valid IDs covering the main control structure
VALID_CLAUSE_IDS = set()
for x in range(1, 15):
    for y in range(1, 10):
        VALID_CLAUSE_IDS.add(f"2-{x}-{y}")


async def enrich_alert(
    db: asyncpg.Connection,
    alert_id: UUID,
    rag_service: RAGService,
    llm_client: LLMClient,
) -> None:
    """
    Service A: Enrichment flow for a single alert.

    1. Load alert from PostgreSQL
    2. Load referenced log events
    3. Check Control-Signal Matrix for matching feature patterns
    4. If CSM match → get specific controls from Qdrant by ID
    5. If no CSM match → semantic search Qdrant
    6. Search confirmed_alerts collection in Qdrant
    7. Assemble prompt
    8. Call LLM
    9. Parse and validate JSON response
    10. Update alert.llm_assessment

    Args:
        db: AsyncPG connection
        alert_id: Alert ID
        rag_service: RAG service instance
        llm_client: LLM client instance
    """
    try:
        # Load alert
        alert = await db.fetchrow("""
            SELECT id, alert_number, domain, entity_principal, anomaly_score,
                   top_features, baseline_deviations, event_ids, triggered_rule_ids,
                   clause_reference, created_at
            FROM alerts
            WHERE id = $1
        """, alert_id)

        if not alert:
            logger.warning(f"Alert {alert_id} not found")
            return

        # Load referenced log events
        event_ids = alert["event_ids"] or []
        events = []
        if event_ids:
            events = await db.fetch("""
                SELECT id, timestamp, event_type, action, principal, resource, result,
                       source_ip, source, domain
                FROM log_events
                WHERE id = ANY($1)
                ORDER BY timestamp DESC
            """, event_ids)

        # Parse top_features and baseline_deviations
        top_features = []
        if alert["top_features"]:
            try:
                features_data = alert["top_features"]
                if isinstance(features_data, str):
                    features_data = json.loads(features_data)
                top_features = features_data if isinstance(features_data, list) else []
            except (json.JSONDecodeError, TypeError):
                top_features = []

        baseline_deviations = {}
        if alert["baseline_deviations"]:
            try:
                dev_data = alert["baseline_deviations"]
                if isinstance(dev_data, str):
                    dev_data = json.loads(dev_data)
                baseline_deviations = dev_data if isinstance(dev_data, dict) else {}
            except (json.JSONDecodeError, TypeError):
                baseline_deviations = {}

        # Check Control-Signal Matrix
        csm_match = await lookup_csm(db, alert["domain"], top_features)
        
        nca_controls = []
        if csm_match:
            # Get specific controls by ID from CSM
            control_ids = [csm_match.get("primary_clause")]
            control_ids.extend(csm_match.get("secondary_clauses", []))
            nca_controls = await rag_service.get_controls_by_ids(control_ids)
        else:
            # Semantic search fallback
            query_text = f"{alert['domain']} {' '.join([f.get('name', '') for f in top_features])} violation"
            nca_controls = await rag_service.search_controls(query_text, top_k=3)

        # Search confirmed alerts
        confirmed_alert_query = f"{alert['domain']} {' '.join([f.get('name', '') for f in top_features])}"
        similar_alerts = await rag_service.search_confirmed_alerts(confirmed_alert_query, top_k=2)

        # Get rule information if available
        rule_names_and_clauses = ""
        triggered_rule_ids = alert.get("triggered_rule_ids") or []
        if triggered_rule_ids:
            rules = await db.fetch("""
                SELECT name, clause_reference FROM rules WHERE id = ANY($1)
            """, triggered_rule_ids)
            rule_names_and_clauses = ", ".join([f"{r['name']} ({r['clause_reference']})" for r in rules])

        # Assemble system prompt
        system_prompt = """You are a cybersecurity compliance analyst specializing in Saudi Arabia's NCA Essential Cybersecurity Controls (ECC 2:2024). You analyze security anomalies detected by an automated monitoring system and assess whether they constitute violations of specific ECC controls.

Rules:
- Analyze the anomaly using ONLY the NCA controls provided in the context. Do not reference controls not provided.
- Cite specific control IDs using the format "2-X-Y" (e.g., "2-2-1", "2-7-3").
- Provide reasoning that a compliance auditor can directly use in a report.
- Assess false positive likelihood based on common benign explanations.
- Respond ONLY in valid JSON. No markdown, no preamble, no explanation outside the JSON structure.

Current user role: Analyst
Data scope: All
"""

        # Assemble user prompt
        controls_text = ""
        for control in nca_controls:
            payload = control.get("payload", {})
            control_id = payload.get("control_id", control.get("id", "unknown"))
            title = payload.get("title", "")
            text = payload.get("text", "")
            controls_text += f"\n{control_id}: {title}\n{text}\n"

        if not controls_text:
            controls_text = "No relevant NCA controls provided."

        similar_alerts_text = ""
        if similar_alerts:
            for similar in similar_alerts:
                payload = similar.get("payload", {})
                similar_alerts_text += f"\nAlert {payload.get('alert_number', 'unknown')}: Domain={payload.get('domain', 'unknown')}, Score={similar.get('score', 'unknown')}\n"
        else:
            similar_alerts_text = "No confirmed historical alerts available yet."

        # Format top features
        features_text = ""
        for i, feature in enumerate(top_features[:3], 1):
            name = feature.get("name", "unknown")
            value = feature.get("value", "unknown")
            deviation = baseline_deviations.get(name, 0.0)
            features_text += f"- {name}: {value} ({deviation:.2f} sigma from baseline)\n"

        # Format event summary
        event_summary = ""
        if events:
            first_event = dict(events[0])
            event_summary = f"""- Event Type: {first_event.get('event_type', 'unknown')}
- Action: {first_event.get('action', 'unknown')}
- Resource: {first_event.get('resource', 'unknown')}
- Result: {first_event.get('result', 'unknown')}
- Source IP: {first_event.get('source_ip', 'unknown')}"""

        user_prompt = f"""## Relevant NCA ECC Controls
{controls_text}

## Similar Past Alerts (Analyst-Confirmed)
{similar_alerts_text}

## Anomaly to Analyze
Alert: {alert['alert_number']}
Domain: {alert['domain']}
Entity: {alert['entity_principal']}
Detection Time: {alert['created_at']}
Anomaly Score: {alert['anomaly_score']}

Top Contributing Features:
{features_text}

Event Summary:
{event_summary}

Related Rule Triggers: {rule_names_and_clauses or 'None'}

## Required Response Format
{{
  "violation_detected": boolean,
  "confidence": float between 0.0 and 1.0,
  "primary_clause": "2-X-Y",
  "secondary_clauses": ["2-X-Y", ...] or [],
  "severity_assessment": "critical" | "high" | "medium" | "low",
  "reasoning": "2-4 sentences explaining the assessment",
  "recommended_action": "specific next step for the analyst",
  "false_positive_likelihood": float between 0.0 and 1.0
}}
"""

        # Call LLM
        llm_response = await llm_client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1000,
            temperature=0.1,
        )

        # Validate response
        validated = validate_llm_response(llm_response)
        
        if not validated:
            # Retry with simplified prompt
            simplified_user_prompt = f"""Analyze this security anomaly from domain {alert['domain']}:
Alert: {alert['alert_number']}
Entity: {alert['entity_principal']}
Anomaly Score: {alert['anomaly_score']}
Top Feature: {features_text}

Provide JSON response with: violation_detected (bool), confidence (0-1), primary_clause (2-X-Y), 
secondary_clauses (list), severity_assessment (critical|high|medium|low), reasoning (string), 
recommended_action (string), false_positive_likelihood (0-1)"""

            llm_response = await llm_client.call(
                system_prompt=system_prompt,
                user_prompt=simplified_user_prompt,
                max_tokens=1000,
                temperature=0.1,
            )
            validated = validate_llm_response(llm_response)

        if validated:
            # Update alert with LLM assessment
            await db.execute("""
                UPDATE alerts
                SET llm_assessment = $1, updated_at = NOW()
                WHERE id = $2
            """, json.dumps(validated), alert_id)
            logger.info(f"Updated alert {alert_id} with LLM assessment")
        else:
            # Mark queue item as failed
            await db.execute("""
                UPDATE llm_queue
                SET status = 'failed', attempts = attempts + 1
                WHERE alert_id = $1
            """, alert_id)
            logger.warning(f"Failed to validate LLM response for alert {alert_id}")

    except Exception as e:
        logger.error(f"Error enriching alert {alert_id}: {e}")
        # Mark queue item as failed
        try:
            await db.execute("""
                UPDATE llm_queue
                SET status = 'failed', attempts = attempts + 1
                WHERE alert_id = $1
            """, alert_id)
        except Exception as inner_e:
            logger.error(f"Error updating queue: {inner_e}")


def validate_llm_response(raw: str) -> Optional[dict]:
    """
    Validate LLM JSON response structure.

    Args:
        raw: Raw LLM response string

    Returns:
        Validated dict or None if invalid
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try stripping markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    # Check required fields
    required = [
        "violation_detected", "confidence", "primary_clause",
        "secondary_clauses", "severity_assessment", "reasoning",
        "recommended_action", "false_positive_likelihood"
    ]
    
    if not all(k in data for k in required):
        return None

    # Type checks
    if not isinstance(data.get("violation_detected"), bool):
        return None
    
    conf = data.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        return None

    fp_likelihood = data.get("false_positive_likelihood")
    if not isinstance(fp_likelihood, (int, float)) or not (0.0 <= fp_likelihood <= 1.0):
        return None

    if data.get("severity_assessment") not in ("critical", "high", "medium", "low"):
        return None

    # Validate clause IDs
    primary = data.get("primary_clause")
    if primary not in VALID_CLAUSE_IDS:
        return None

    secondary = data.get("secondary_clauses", [])
    if not isinstance(secondary, list):
        return None
    
    data["secondary_clauses"] = [c for c in secondary if c in VALID_CLAUSE_IDS]

    return data


async def lookup_csm(
    db: asyncpg.Connection, domain: str, top_features: list[dict]
) -> Optional[dict]:
    """
    Query Control-Signal Matrix for matching feature patterns.

    Args:
        db: AsyncPG connection
        domain: Domain name
        top_features: List of top feature dicts

    Returns:
        Matching CSM entry or None
    """
    try:
        if not top_features:
            return None

        feature_names = [f.get("name", "") for f in top_features]
        
        # Query CSM for matching domain and features
        csm_entry = await db.fetchrow("""
            SELECT matrix_id, primary_clause, secondary_clauses, severity_guidance
            FROM control_signal_matrix
            WHERE domain = $1
              AND trigger_features && $2::text[]
            LIMIT 1
        """, domain, feature_names)

        if csm_entry:
            return dict(csm_entry)
        
        return None

    except Exception as e:
        logger.debug(f"Error looking up CSM: {e}")
        return None
