"""Service B: AI Chatbot for SAIA V4."""

import logging
import re
import asyncpg
from typing import AsyncGenerator, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from .llm_client import LLMClient
from .rag_service import RAGService

logger = logging.getLogger(__name__)


def classify_intent(message: str) -> str:
    """
    Classify user message intent using keyword heuristics.

    Returns one of: ALERT_INVESTIGATION, LOG_QUERY, COMPLIANCE_STATUS,
    REGULATORY_GUIDANCE, SYSTEM_STATUS, GENERAL
    """
    msg = message.lower()

    # ALERT_INVESTIGATION: references alert numbers
    if re.search(r'alt-\d{4}-\d+', msg):
        return "ALERT_INVESTIGATION"

    # LOG_QUERY: list, show, find, search, count
    if any(w in msg for w in ["show", "list", "find", "search", "how many", "count"]):
        return "LOG_QUERY"

    # COMPLIANCE_STATUS: compliance, posture
    if any(w in msg for w in ["compliant", "compliance", "posture", "status"]):
        return "COMPLIANCE_STATUS"

    # REGULATORY_GUIDANCE: ECC clause reference
    if re.search(r'ecc\s+\d+-\d+', msg) or re.search(r'2-\d+-\d+', msg):
        return "REGULATORY_GUIDANCE"

    # SYSTEM_STATUS: health, queue, latency, model
    if any(w in msg for w in ["health", "queue", "latency", "model", "baseline"]):
        return "SYSTEM_STATUS"

    return "GENERAL"


def extract_log_filters(message: str) -> dict:
    """
    Extract structured filter parameters from user message.

    Returns dict with optional keys: since, result, event_type, domain
    """
    filters = {}
    msg = message.lower()

    # Time range
    if "today" in msg:
        filters["since_days"] = 1
    elif "this week" in msg or "last 7 days" in msg:
        filters["since_days"] = 7
    elif "this month" in msg:
        filters["since_days"] = 30

    # Result filter
    if "failed" in msg or "failure" in msg:
        filters["result"] = "failure"
    elif "success" in msg:
        filters["result"] = "success"

    # Event type
    if "login" in msg or "authentication" in msg:
        filters["event_type"] = "authentication"
    elif "file" in msg or "download" in msg:
        filters["event_type"] = "file_access"

    # Domain
    for domain in ["IAM", "Network", "Application", "Cloud"]:
        if domain.lower() in msg:
            filters["domain"] = domain
            break

    return filters


async def run_log_query(
    db: asyncpg.Connection, filters: dict, data_scope: list[str]
) -> dict:
    """
    Build and execute parameterized log query based on filters.

    Args:
        db: AsyncPG connection
        filters: Filter dict
        data_scope: User's allowed domains

    Returns:
        {"count": int, "rows": list[dict], "filters_applied": dict}
    """
    try:
        conditions = ["domain = ANY($1)"]
        params = [data_scope]
        param_index = 2

        # Time filter
        if "since_days" in filters:
            days = filters["since_days"]
            conditions.append(f"timestamp > NOW() - INTERVAL '{days} days'")

        # Result filter
        if "result" in filters:
            conditions.append(f"result = ${param_index}")
            params.append(filters["result"])
            param_index += 1

        # Event type filter
        if "event_type" in filters:
            conditions.append(f"event_type = ${param_index}")
            params.append(filters["event_type"])
            param_index += 1

        # Domain override (single domain)
        if "domain" in filters:
            conditions[0] = f"domain = ${param_index}"
            params[0] = filters["domain"]
            param_index += 1

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT id, timestamp, event_type, action, principal, resource, result,
                   source_ip, domain, source
            FROM log_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT 100
        """

        rows = await db.fetch(query, *params)

        return {
            "count": len(rows),
            "rows": [dict(r) for r in rows],
            "filters_applied": filters,
        }

    except Exception as e:
        logger.error(f"Error running log query: {e}")
        return {"count": 0, "rows": [], "filters_applied": filters}


async def build_context(
    db: asyncpg.Connection,
    message: str,
    intent: str,
    user_data_scope: list[str],
    rag_service: RAGService,
) -> str:
    """
    Build context string for LLM based on intent and tool calls.

    Args:
        db: AsyncPG connection
        message: User message
        intent: Classified intent
        user_data_scope: User's allowed domains
        rag_service: RAG service instance

    Returns:
        Context string to include in LLM prompt
    """
    context = ""

    try:
        if intent == "ALERT_INVESTIGATION":
            # Extract alert number from message
            match = re.search(r'alt-(\d{4})-(\d+)', message.lower())
            if match:
                alert_number = f"ALT-{match.group(1)}-{match.group(2)}"
                alert = await db.fetchrow("""
                    SELECT id, severity, status, anomaly_score, top_features,
                           llm_assessment, analyst_verdict
                    FROM alerts
                    WHERE alert_number = $1
                      AND domain = ANY($2)
                """, alert_number, user_data_scope)
                
                if alert:
                    context = f"""Alert Found:
- Number: {alert_number}
- Severity: {alert['severity']}
- Status: {alert['status']}
- Anomaly Score: {alert['anomaly_score']}
- Verdict: {alert['analyst_verdict'] or 'Pending'}
"""
                    if alert.get("llm_assessment"):
                        try:
                            assessment = alert["llm_assessment"]
                            if isinstance(assessment, str):
                                assessment = __import__('json').loads(assessment)
                            context += f"- Primary Clause: {assessment.get('primary_clause', 'N/A')}\n"
                        except Exception:
                            pass

        elif intent == "LOG_QUERY":
            filters = extract_log_filters(message)
            result = await run_log_query(db, filters, user_data_scope)
            context = f"""Query Results:
- Events found: {result['count']}
- Filters applied: {result['filters_applied']}
- Sample events (first 5):
"""
            for event in result["rows"][:5]:
                context += f"  {event['timestamp']}: {event['event_type']} {event['action']} on {event['resource']}\n"

        elif intent == "COMPLIANCE_STATUS":
            alerts_by_clause = await db.fetch("""
                SELECT clause_reference, COUNT(*) as open_count,
                       SUM(CASE WHEN status IN ('resolved', 'verified') THEN 1 ELSE 0 END) as resolved_count
                FROM alerts
                WHERE domain = ANY($1)
                GROUP BY clause_reference
                ORDER BY open_count DESC
                LIMIT 10
            """, user_data_scope)

            context = "Current Compliance Status by Control:\n"
            for row in alerts_by_clause:
                clause = row["clause_reference"] or "Unknown"
                context += f"- {clause}: {row['open_count']} open, {row['resolved_count']} resolved\n"

        elif intent == "REGULATORY_GUIDANCE":
            # Extract clause reference
            match = re.search(r'2-(\d+)-(\d+)', message)
            if match:
                clause_id = f"2-{match.group(1)}-{match.group(2)}"
                controls = await rag_service.search_controls(clause_id, top_k=1)
                if controls:
                    context = f"""NCA Control {clause_id}:
"""
                    for control in controls:
                        payload = control.get("payload", {})
                        context += f"{payload.get('title', 'N/A')}\n"
                        context += f"{payload.get('text', 'No description available')[:500]}...\n"

        elif intent == "SYSTEM_STATUS":
            # Get dashboard stats
            alert_counts = await db.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                    SUM(CASE WHEN status = 'investigating' THEN 1 ELSE 0 END) as investigating,
                    SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical
                FROM alerts
                WHERE domain = ANY($1)
            """, user_data_scope)

            if alert_counts:
                context = f"""System Status:
- Total alerts: {alert_counts['total']}
- Open: {alert_counts['open']}
- Investigating: {alert_counts['investigating']}
- Critical: {alert_counts['critical']}
"""

    except Exception as e:
        logger.error(f"Error building context: {e}")
        context = "Unable to retrieve additional context."

    return context


async def handle_message(
    db: asyncpg.Connection,
    session_id: UUID,
    user_id: UUID,
    username: str,
    role: str,
    data_scope: list[str],
    message: str,
    llm_client: LLMClient,
    rag_service: RAGService,
) -> AsyncGenerator[str, None]:
    """
    Handle a chat message: classify, build context, stream LLM response, save history.

    Args:
        db: AsyncPG connection
        session_id: Chat session ID
        user_id: User ID
        username: Username
        role: User role
        data_scope: User's allowed domains
        message: User message
        llm_client: LLM client
        rag_service: RAG service

    Yields:
        Chunks of LLM response
    """
    try:
        # Validate session
        session_valid = await check_session_valid(db, session_id)
        if not session_valid:
            yield "Error: Session expired or not found. Please create a new session."
            return

        # Save user message to history
        user_msg_id = await db.fetchval("""
            INSERT INTO chat_history (session_id, user_id, role, content)
            VALUES ($1, $2, 'user', $3)
            RETURNING id
        """, session_id, user_id, message)

        # Classify intent
        intent = classify_intent(message)

        # Build context from tool calls
        context = await build_context(db, message, intent, data_scope, rag_service)

        # Get conversation history for context (last 5 messages)
        history = await get_session_history(db, session_id, user_id, limit=5)
        history_text = "\n".join([
            f"{h['role'].upper()}: {h['content'][:100]}..." for h in history if h['id'] != user_msg_id
        ])

        # Assemble system prompt
        system_prompt = f"""You are SAIA Assistant, an AI security analyst for a Saudi organization. You help admins, compliance officers, and analysts investigate security alerts, query log data, and understand NCA Essential Cybersecurity Controls.

You have access to query results provided in the CONTEXT section below. Base your answers ONLY on the provided context. If the context doesn't contain enough information, say so.

Rules:
- Never reveal raw PII. Use entity hashes or identifiers only.
- Never make definitive compliance judgments. Provide evidence and reasoning; let humans decide.
- Cite specific ECC control IDs (e.g., "2-2-1") when discussing regulatory requirements.
- If unsure, say so. Never fabricate data.
- Keep responses concise and actionable.
- When showing log data, present it in structured tables using markdown.
- Always indicate the time range and scope of data you present.

Current user: {username}
Role: {role}
Data scope: {", ".join(data_scope)}
Current time: {datetime.now(timezone.utc).isoformat()}
"""

        # Assemble user prompt
        user_prompt = f"""CONTEXT:
{context}

CONVERSATION HISTORY:
{history_text}

USER MESSAGE:
{message}

Respond based on the context provided. If additional information is needed, ask the user."""

        # Stream LLM response
        response_text = ""
        async for chunk in llm_client.call_streaming(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2000,
            temperature=0.1,
        ):
            response_text += chunk
            yield chunk

        # Save assistant message to history
        await db.execute("""
            INSERT INTO chat_history (session_id, user_id, role, content)
            VALUES ($1, $2, 'assistant', $3)
        """, session_id, user_id, response_text)

        # Update session last_active_at
        await db.execute("""
            UPDATE chat_sessions
            SET last_active_at = NOW()
            WHERE id = $1
        """, session_id)

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        yield f"Error processing message: {str(e)}"


async def create_session(db: asyncpg.Connection, user_id: UUID) -> UUID:
    """
    Create a new chat session.

    Args:
        db: AsyncPG connection
        user_id: User ID

    Returns:
        Session UUID
    """
    try:
        session_id = await db.fetchval("""
            INSERT INTO chat_sessions (user_id)
            VALUES ($1)
            RETURNING id
        """, user_id)
        return UUID(session_id)
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise


async def get_session_history(
    db: asyncpg.Connection,
    session_id: UUID,
    user_id: UUID,
    limit: int = 50,
) -> list[dict]:
    """
    Load conversation history for a session.

    Args:
        db: AsyncPG connection
        session_id: Session ID
        user_id: User ID (for authorization)
        limit: Max messages to return

    Returns:
        List of message dicts
    """
    try:
        messages = await db.fetch("""
            SELECT id, role, content, created_at
            FROM chat_history
            WHERE session_id = $1
              AND (SELECT user_id FROM chat_sessions WHERE id = $1) = $2
            ORDER BY created_at ASC
            LIMIT $3
        """, session_id, user_id, limit)

        return [dict(m) for m in messages]
    except Exception as e:
        logger.error(f"Error loading session history: {e}")
        return []


async def check_session_valid(db: asyncpg.Connection, session_id: UUID) -> bool:
    """
    Check if session exists and is not expired (24h).

    Args:
        db: AsyncPG connection
        session_id: Session ID

    Returns:
        True if valid
    """
    try:
        session = await db.fetchrow("""
            SELECT id, created_at, last_active_at
            FROM chat_sessions
            WHERE id = $1
        """, session_id)

        if not session:
            return False

        # Check if expired (24 hours)
        now = datetime.now(timezone.utc)
        last_active = session["last_active_at"]
        if isinstance(last_active, str):
            last_active = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
        
        if not last_active.tzinfo:
            last_active = last_active.replace(tzinfo=timezone.utc)

        expires_at = last_active + timedelta(hours=24)
        return now < expires_at

    except Exception as e:
        logger.error(f"Error checking session: {e}")
        return False
