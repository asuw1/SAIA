"""Feedback (TP/FP) processing service for SAIA V4."""

import logging
import json
from uuid import UUID
from datetime import datetime, timezone
import asyncpg

from .rag_service import RAGService

logger = logging.getLogger(__name__)


async def submit_feedback(
    db: asyncpg.Connection,
    alert_id: UUID,
    verdict: str,
    comment: str,
    user_id: UUID,
    rag_service: RAGService,
) -> None:
    """
    Submit TP/FP feedback on an alert.

    Steps:
    1. Update alert (verdict, comment, status, resolved_at)
    2. Log to audit_log
    3. If true_positive: add to Qdrant confirmed_alerts collection

    Args:
        db: AsyncPG connection
        alert_id: Alert ID
        verdict: "true_positive" or "false_positive"
        comment: Analyst comment
        user_id: User ID (analyst)
        rag_service: RAG service instance
    """
    try:
        if verdict not in ("true_positive", "false_positive"):
            raise ValueError(f"Invalid verdict: {verdict}")

        # Update alert
        new_status = "resolved" if verdict == "true_positive" else "false_positive"
        
        await db.execute("""
            UPDATE alerts
            SET analyst_verdict = $1,
                analyst_comment = $2,
                status = $3,
                resolved_at = NOW(),
                updated_at = NOW()
            WHERE id = $4
        """, verdict, comment, new_status, alert_id)

        # Log to audit trail
        await db.execute("""
            INSERT INTO audit_log (user_id, action, resource, details)
            VALUES ($1, 'alert_feedback', $2, $3)
        """, user_id, str(alert_id), json.dumps({
            "verdict": verdict,
            "comment": comment
        }))

        logger.info(f"Submitted feedback for alert {alert_id}: {verdict}")

        # If true positive, add to confirmed alerts collection
        if verdict == "true_positive":
            await add_to_confirmed_alerts(db, alert_id, rag_service)

    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise


async def add_to_confirmed_alerts(
    db: asyncpg.Connection,
    alert_id: UUID,
    rag_service: RAGService,
) -> None:
    """
    Add confirmed alert to Qdrant for future context.

    Args:
        db: AsyncPG connection
        alert_id: Alert ID
        rag_service: RAG service instance
    """
    try:
        # Load alert
        alert = await db.fetchrow("""
            SELECT id, alert_number, domain, severity, anomaly_score,
                   top_features, analyst_comment, analyst_verdict,
                   llm_assessment
            FROM alerts
            WHERE id = $1
        """, alert_id)

        if not alert:
            logger.warning(f"Alert {alert_id} not found for confirmed storage")
            return

        # Build summary text for embedding
        top_features_str = ""
        if alert.get("top_features"):
            try:
                features = alert["top_features"]
                if isinstance(features, str):
                    features = json.loads(features)
                if isinstance(features, list):
                    top_features_str = ", ".join([f.get("name", "") for f in features])
            except (json.JSONDecodeError, TypeError):
                pass

        clause_ref = "Unknown"
        confidence = 0.0
        try:
            assessment = alert.get("llm_assessment")
            if assessment:
                if isinstance(assessment, str):
                    assessment = json.loads(assessment)
                clause_ref = assessment.get("primary_clause", "Unknown")
                confidence = assessment.get("confidence", 0.0)
        except (json.JSONDecodeError, TypeError):
            pass

        summary_text = f"""
        Domain: {alert['domain']}
        Severity: {alert['severity']}
        Anomaly Score: {alert['anomaly_score']}
        Features: {top_features_str}
        Verdict: {alert['analyst_verdict']}
        Clause: {clause_ref}
        Comment: {alert.get('analyst_comment', '')}
        """

        # Embed and store in Qdrant
        payload = {
            "alert_id": str(alert_id),
            "alert_number": alert["alert_number"],
            "domain": alert["domain"],
            "severity": alert["severity"],
            "anomaly_score": alert["anomaly_score"],
            "top_features": top_features_str,
            "analyst_verdict": alert["analyst_verdict"],
            "clause": clause_ref,
            "confidence": confidence,
            "comment": alert.get("analyst_comment", ""),
        }

        await rag_service.upsert_confirmed_alert(
            alert_id=alert_id,
            summary_text=summary_text,
            payload=payload,
        )

        logger.info(f"Added alert {alert_id} to confirmed_alerts collection")

    except Exception as e:
        logger.error(f"Error adding to confirmed alerts: {e}")
