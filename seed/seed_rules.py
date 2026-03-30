"""Seed script for loading starter rules into PostgreSQL."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings

logger = logging.getLogger(__name__)


async def get_db_pool() -> asyncpg.pool.Pool:
    """Create an asyncpg connection pool."""
    return await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        min_size=5,
        max_size=20,
    )


async def seed_rules(db_pool: asyncpg.pool.Pool) -> None:
    """
    Load starter rules into PostgreSQL rules table.

    Creates 5 seed rules:
    a. Brute Force Login Detection (IAM, 2-2-1, critical)
    b. Unencrypted Data Transfer (Network, 2-8-1, high)
    c. Dormant Account Reactivation (IAM, 2-2-4, medium)
    d. Privilege Escalation (IAM, 2-2-4, critical)
    e. Log Volume Anomaly (Application, 2-13-1, medium)

    Args:
        db_pool: AsyncPG connection pool
    """
    logger.info("Starting rules seeding")

    rules = [
        {
            "name": "Brute Force Login Detection",
            "description": "Detect multiple failed login attempts from different IPs",
            "domain": "Identity and Access Management",
            "clause_reference": "2-2-1",
            "severity": "critical",
            "conditions": {
                "field_checks": [
                    {
                        "field": "event_type",
                        "operator": "equals",
                        "value": "login_failed",
                    },
                    {
                        "field": "result",
                        "operator": "equals",
                        "value": "failure",
                    },
                ],
                "aggregation": {
                    "group_by": ["principal", "source_ip"],
                    "window_minutes": 30,
                    "count_threshold": 10,
                },
            },
        },
        {
            "name": "Unencrypted Data Transfer",
            "description": "Detect data transfers using unencrypted protocols",
            "domain": "Network Security",
            "clause_reference": "2-8-1",
            "severity": "high",
            "conditions": {
                "field_checks": [
                    {
                        "field": "action",
                        "operator": "contains",
                        "value": "transfer",
                    },
                    {
                        "field": "raw_log",
                        "operator": "regex",
                        "value": "ftp|http|telnet",
                    },
                ],
                "aggregation": None,
            },
        },
        {
            "name": "Dormant Account Reactivation",
            "description": "Detect dormant accounts becoming active",
            "domain": "Identity and Access Management",
            "clause_reference": "2-2-4",
            "severity": "medium",
            "conditions": {
                "field_checks": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "login",
                    },
                    {
                        "field": "principal",
                        "operator": "contains",
                        "value": "dormant",
                    },
                ],
                "aggregation": None,
            },
        },
        {
            "name": "Privilege Escalation",
            "description": "Detect unexpected privilege level escalation",
            "domain": "Identity and Access Management",
            "clause_reference": "2-2-4",
            "severity": "critical",
            "conditions": {
                "field_checks": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "role_change",
                    },
                    {
                        "field": "raw_log",
                        "operator": "regex",
                        "value": "admin|root|privilege",
                    },
                ],
                "aggregation": None,
            },
        },
        {
            "name": "Log Volume Anomaly",
            "description": "Detect unusual spike in log volume indicating potential attack",
            "domain": "Application Security",
            "clause_reference": "2-13-1",
            "severity": "medium",
            "conditions": {
                "field_checks": [
                    {
                        "field": "event_type",
                        "operator": "equals",
                        "value": "error",
                    },
                ],
                "aggregation": {
                    "group_by": ["source"],
                    "window_minutes": 10,
                    "count_threshold": 100,
                },
            },
        },
    ]

    async with db_pool.acquire() as db:
        successfully_seeded = 0
        failed_rules = []

        for rule_data in rules:
            try:
                rule_id = str(uuid4())

                # Check if rule already exists by name
                existing = await db.fetchval(
                    """
                    SELECT id FROM rules WHERE name = $1
                    """,
                    rule_data["name"],
                )

                if existing:
                    logger.info(f"Rule '{rule_data['name']}' already exists, skipping")
                    continue

                # Insert the rule
                await db.execute(
                    """
                    INSERT INTO rules
                    (id, name, description, domain, clause_reference, severity,
                     conditions, is_active, version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    rule_id,
                    rule_data["name"],
                    rule_data["description"],
                    rule_data["domain"],
                    rule_data["clause_reference"],
                    rule_data["severity"],
                    json.dumps(rule_data["conditions"]),
                    True,
                    "1.0",
                )

                successfully_seeded += 1
                logger.info(f"Seeded rule: {rule_data['name']}")

            except Exception as e:
                logger.error(f"Failed to seed rule '{rule_data.get('name')}': {e}")
                failed_rules.append(rule_data.get("name"))

    logger.info(
        f"Completed rules seeding: {successfully_seeded} successfully seeded, "
        f"{len(failed_rules)} failed"
    )

    if failed_rules:
        logger.warning(f"Failed rules: {', '.join(failed_rules)}")


async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    db_pool = None
    try:
        db_pool = await get_db_pool()
        logger.info("Connected to database")
        await seed_rules(db_pool)
        logger.info("Rules seeding completed successfully")
    except Exception as e:
        logger.error(f"Rules seeding failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")


if __name__ == "__main__":
    asyncio.run(main())
