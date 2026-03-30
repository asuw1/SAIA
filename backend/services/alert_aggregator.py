"""Alert aggregation and deduplication service for SAIA V4."""

import logging
import json
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
import asyncpg

from .websocket import get_connection_manager

logger = logging.getLogger(__name__)

DEDUP_WINDOW_HOURS = 1


async def aggregate_alert(
    db: asyncpg.Connection,
    event_id: UUID,
    domain: str,
    entity: str,
    clause: str,
    severity: str,
    source: str,
    anomaly_score: Optional[float] = None,
    top_features: Optional[dict] = None,
    baseline_deviations: Optional[dict] = None,
    rule_id: Optional[UUID] = None,
) -> UUID:
    """
    Create or update alert using deduplication logic.

    Check for existing open alert with same entity+domain+clause within DEDUP_WINDOW_HOURS.
    If found, append event; if not, create new alert and queue for LLM analysis.

    Args:
        db: AsyncPG connection
        event_id: Log event ID
        domain: Domain name
        entity: Entity principal
        clause: Clause reference (may be None for ML-only alerts without CSM match)
        severity: Severity level (from rule or computed from score)
        source: "rule", "ai", or "both"
        anomaly_score: ML anomaly score (optional)
        top_features: Top contributing features dict
        baseline_deviations: Baseline deviation scores dict
        rule_id: Rule ID if rule-triggered (optional)

    Returns:
        Alert ID (UUID)
    """
    try:
        # Check for existing open alert with same dedup fingerprint
        existing = await db.fetchrow("""
            SELECT id, event_ids, triggered_rule_ids, source
            FROM alerts
            WHERE entity_principal = $1
              AND domain = $2
              AND (clause_reference = $3 OR (clause_reference IS NULL AND $3 IS NULL))
              AND status IN ('open', 'investigating')
              AND created_at > NOW() - INTERVAL '1 hour'
            ORDER BY created_at DESC
            LIMIT 1
        """, entity, domain, clause)

        if existing:
            # Append to existing alert
            new_event_ids = list(existing["event_ids"] or []) + [str(event_id)]
            
            new_source = "both"
            if existing["source"] != source:
                new_source = "both"
            else:
                new_source = source

            new_rule_ids = list(existing["triggered_rule_ids"] or [])
            if rule_id and str(rule_id) not in new_rule_ids:
                new_rule_ids.append(str(rule_id))

            await db.execute("""
                UPDATE alerts
                SET event_ids = $1, source = $2, triggered_rule_ids = $3, updated_at = NOW()
                WHERE id = $4
            """, new_event_ids, new_source, new_rule_ids if new_rule_ids else None, existing["id"])

            logger.info(f"Updated alert {existing['id']} with event {event_id}")
            return UUID(existing["id"])

        else:
            # Create new alert
            alert_number = await generate_alert_number(db)
            
            # Compute severity: prefer rule severity, else compute from score
            final_severity = severity
            if source == "ai" and anomaly_score is not None:
                final_severity = compute_severity(anomaly_score)

            alert_id = await db.fetchval("""
                INSERT INTO alerts (
                    alert_number, domain, severity, status, source,
                    entity_principal, clause_reference, anomaly_score,
                    top_features, baseline_deviations, triggered_rule_ids, event_ids
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """,
            alert_number, domain, final_severity, "open", source,
            entity, clause, anomaly_score,
            json.dumps(top_features) if top_features else None,
            json.dumps(baseline_deviations) if baseline_deviations else None,
            [str(rule_id)] if rule_id else None,
            [str(event_id)])

            # Enqueue for LLM analysis
            priority = severity_to_priority(final_severity)
            await enqueue_for_llm(db, UUID(alert_id), priority)

            # Broadcast to connected clients
            ws_manager = get_connection_manager()
            await ws_manager.broadcast_new_alert(UUID(alert_id), alert_number, final_severity)

            logger.info(f"Created new alert {alert_id} for event {event_id}")
            return UUID(alert_id)

    except Exception as e:
        logger.error(f"Error in aggregate_alert: {e}")
        raise


async def generate_alert_number(db: asyncpg.Connection) -> str:
    """
    Generate unique alert number in format "ALT-{year}-{seq:04d}".

    Args:
        db: AsyncPG connection

    Returns:
        Alert number string
    """
    try:
        current_year = datetime.now(timezone.utc).year
        
        # Get next sequence number for current year
        seq = await db.fetchval("""
            SELECT COALESCE(MAX(CAST(SPLIT_PART(alert_number, '-', 3) AS INTEGER)), 0) + 1
            FROM alerts
            WHERE alert_number LIKE $1
        """, f"ALT-{current_year}-%")
        
        alert_number = f"ALT-{current_year}-{seq:04d}"
        return alert_number

    except Exception as e:
        logger.error(f"Error generating alert number: {e}")
        # Fallback: use timestamp-based number
        timestamp_part = int(datetime.now(timezone.utc).timestamp()) % 10000
        return f"ALT-{timestamp_part:04d}"


def compute_severity(anomaly_score: Optional[float]) -> str:
    """
    Map anomaly score to severity level.

    Args:
        anomaly_score: Anomaly score 0-1

    Returns:
        Severity: "critical", "high", "medium", or "low"
    """
    if anomaly_score is None:
        return "medium"
    
    if anomaly_score > 0.9:
        return "critical"
    elif anomaly_score > 0.75:
        return "high"
    elif anomaly_score > 0.6:
        return "medium"
    else:
        return "low"


def severity_to_priority(severity: str) -> int:
    """
    Map severity to queue priority (1=critical, 4=low).

    Args:
        severity: Severity level

    Returns:
        Priority integer 1-4
    """
    severity_map = {
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 4,
    }
    return severity_map.get(severity, 3)


async def enqueue_for_llm(db: asyncpg.Connection, alert_id: UUID, priority: int) -> None:
    """
    Insert alert into LLM queue for enrichment.

    Args:
        db: AsyncPG connection
        alert_id: Alert ID
        priority: Priority 1-4
    """
    try:
        await db.execute("""
            INSERT INTO llm_queue (alert_id, priority, status)
            VALUES ($1, $2, 'pending')
        """, alert_id, priority)
        logger.debug(f"Queued alert {alert_id} for LLM with priority {priority}")
    except Exception as e:
        logger.error(f"Error enqueueing alert for LLM: {e}")
