#!/usr/bin/env python3
"""Export labeled alert feedback and event data from SAIA V4.

Queries alerts with analyst verdicts (true_positive / false_positive),
joins with log events, and exports as CSV with feature values for model
training and analysis.

Uses asyncpg directly (matching the V4 backend pattern) rather than ORM models.
"""

import argparse
import asyncio
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 25 ML feature names (must match backend/services/feature_extractor.py)
FEATURE_NAMES = [
    "hour_of_day",
    "day_of_week",
    "is_business_hours",
    "is_weekend",
    "minutes_since_last_event",
    "events_in_last_hour",
    "unique_resources_1h",
    "unique_actions_1h",
    "failed_action_ratio_1h",
    "privilege_level",
    "is_new_resource",
    "is_new_action",
    "deviation_from_hourly_baseline",
    "deviation_from_daily_baseline",
    "source_ip_is_known",
    "source_country_is_usual",
    "asset_criticality",
    "principal_risk_score",
    "concurrent_sessions",
    "is_sensitive_resource",
    "entity_event_volume_zscore",
    "entity_error_rate_zscore",
    "entity_resource_diversity_zscore",
    "entity_privilege_escalation_rate",
    "cross_entity_correlation_score",
]


def _db_url() -> str:
    """Build a raw asyncpg DSN from environment (no SQLAlchemy prefix)."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "saia_db")
    user = os.getenv("DB_USER", "saia")
    pw   = os.getenv("DB_PASSWORD", "saia_password")
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"


async def fetch_verdicted_alerts(pool) -> list[dict]:
    """Fetch all alerts that have an analyst verdict."""
    query = """
        SELECT id, alert_number, domain, severity, analyst_verdict,
               anomaly_score, top_features, baseline_deviations,
               event_ids, analyst_comment, created_at
        FROM alerts
        WHERE analyst_verdict IN ('true_positive', 'false_positive')
        ORDER BY created_at
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    logger.info(f"Found {len(rows)} verdicted alerts")
    return [dict(r) for r in rows]


async def fetch_events_by_ids(pool, event_ids: list) -> list[dict]:
    """Fetch log events by their UUIDs."""
    if not event_ids:
        return []
    query = """
        SELECT id, timestamp, source, event_type, principal, action,
               resource, result, source_ip, asset_id, domain,
               quality_score, anomaly_score, is_flagged
        FROM log_events
        WHERE id = ANY($1::uuid[])
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, event_ids)
    return [dict(r) for r in rows]


def _extract_feature_values(top_features, baseline_deviations) -> dict:
    """Extract feature values from the JSONB columns stored on the alert.

    top_features is a list[dict] like:
        [{"name": "hour_of_day", "value": 3, "deviation_sigma": 4.2}, ...]
    baseline_deviations is a dict like:
        {"hour_of_day": 4.2, "failed_action_ratio_1h": 3.1, ...}
    """
    values = {name: "" for name in FEATURE_NAMES}

    # Fill from top_features list
    if isinstance(top_features, list):
        for entry in top_features:
            if isinstance(entry, dict):
                name = entry.get("name", "")
                if name in values:
                    values[name] = entry.get("value", "")

    # Fill blanks from baseline_deviations (these are z-scores, useful context)
    if isinstance(baseline_deviations, dict):
        for name, zscore in baseline_deviations.items():
            if name in values and values[name] == "":
                values[name] = zscore

    return values


async def export_feedback(output_file: str = "feedback_export.csv") -> None:
    """Export all feedback data to CSV."""
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg is required.  pip install asyncpg")
        sys.exit(1)

    dsn = _db_url()
    logger.info("=" * 60)
    logger.info("SAIA V4 — Alert Feedback Export")
    logger.info("=" * 60)
    logger.info(f"Connecting to {dsn.split('@')[-1]} ...")

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

    try:
        alerts = await fetch_verdicted_alerts(pool)
        if not alerts:
            logger.warning("No verdicted alerts found — nothing to export.")
            return

        csv_rows = []

        for i, alert in enumerate(alerts):
            logger.info(
                f"  [{i+1}/{len(alerts)}] {alert['alert_number']} "
                f"({alert['analyst_verdict']})"
            )
            # Fetch associated events (for reference only; features come from
            # the alert's JSONB columns which are pre-computed).
            events = await fetch_events_by_ids(pool, alert.get("event_ids") or [])

            features = _extract_feature_values(
                alert.get("top_features"),
                alert.get("baseline_deviations"),
            )

            row = {
                "alert_number": alert["alert_number"],
                "domain": alert["domain"],
                "severity": alert["severity"],
                "verdict": alert["analyst_verdict"],
                "anomaly_score": alert.get("anomaly_score", ""),
                "event_count": len(events),
                **features,
                "comment": alert.get("analyst_comment", ""),
            }
            csv_rows.append(row)

        # Write CSV
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "alert_number", "domain", "severity", "verdict",
            "anomaly_score", "event_count",
            *FEATURE_NAMES,
            "comment",
        ]

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        # Summary
        tp = sum(1 for r in csv_rows if r["verdict"] == "true_positive")
        fp = sum(1 for r in csv_rows if r["verdict"] == "false_positive")
        domains = {}
        for r in csv_rows:
            domains[r["domain"]] = domains.get(r["domain"], 0) + 1

        logger.info("\n" + "=" * 60)
        logger.info("Export Summary")
        logger.info("=" * 60)
        logger.info(f"Total alerts exported: {len(csv_rows)}")
        logger.info(f"  True positives:  {tp}")
        logger.info(f"  False positives: {fp}")
        logger.info("By domain:")
        for d, c in sorted(domains.items()):
            logger.info(f"  {d}: {c}")
        logger.info(f"\nSaved to: {output_path.absolute()}")
        logger.info("=" * 60)

    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Export verdicted alerts and event data as CSV for analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/export_feedback.py
  python scripts/export_feedback.py --output /data/exports/feedback_2025.csv
        """,
    )
    parser.add_argument(
        "--output", default="feedback_export.csv",
        help="Output CSV filename (default: feedback_export.csv)",
    )
    args = parser.parse_args()
    asyncio.run(export_feedback(output_file=args.output))


if __name__ == "__main__":
    main()
