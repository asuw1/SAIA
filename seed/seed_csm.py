"""Seed script for loading control signal matrix into PostgreSQL."""

import asyncio
import json
import logging
import sys
from pathlib import Path

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


async def seed_csm(db_pool: asyncpg.pool.Pool) -> None:
    """
    Load control signal matrix entries from JSON file into PostgreSQL.

    Flow:
    1. Load control_signal_matrix.json from seed directory
    2. For each entry:
       - Extract matrix_id, domain, anomaly_pattern, primary_clause, etc.
       - Upsert to control_signal_matrix table
    3. Log results

    Args:
        db_pool: AsyncPG connection pool
    """
    logger.info("Starting control signal matrix seeding")

    # Load CSM from JSON file
    csm_path = Path(__file__).parent / "control_signal_matrix.json"

    if not csm_path.exists():
        logger.error(f"CSM file not found: {csm_path}")
        raise FileNotFoundError(f"CSM file not found at {csm_path}")

    try:
        with open(csm_path, "r") as f:
            csm_entries = json.load(f)
        logger.info(f"Loaded {len(csm_entries)} CSM entries from {csm_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse CSM JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load CSM file: {e}")
        raise

    # Upsert entries to database
    async with db_pool.acquire() as db:
        successfully_seeded = 0
        failed_entries = []

        for entry in csm_entries:
            try:
                matrix_id = entry.get("matrix_id")
                domain = entry.get("domain")
                anomaly_pattern = entry.get("anomaly_pattern", {})
                primary_clause = entry.get("primary_clause")
                secondary_clauses = entry.get("secondary_clauses", [])
                severity_guidance = entry.get("severity_guidance")
                explanation_template = entry.get("explanation_template")

                if not matrix_id:
                    logger.warning("Skipping entry with missing matrix_id")
                    failed_entries.append("unknown")
                    continue

                # Check if entry already exists
                existing = await db.fetchval(
                    """
                    SELECT id FROM control_signal_matrix WHERE matrix_id = $1
                    """,
                    matrix_id,
                )

                if existing:
                    logger.debug(f"CSM entry {matrix_id} already exists, updating")
                    await db.execute(
                        """
                        UPDATE control_signal_matrix
                        SET domain = $2, anomaly_pattern = $3, primary_clause = $4,
                            secondary_clauses = $5, severity_guidance = $6,
                            explanation_template = $7
                        WHERE matrix_id = $1
                        """,
                        matrix_id,
                        domain,
                        json.dumps(anomaly_pattern),
                        primary_clause,
                        secondary_clauses,
                        severity_guidance,
                        explanation_template,
                    )
                else:
                    # Insert new entry
                    await db.execute(
                        """
                        INSERT INTO control_signal_matrix
                        (matrix_id, domain, anomaly_pattern, primary_clause,
                         secondary_clauses, severity_guidance, explanation_template)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        matrix_id,
                        domain,
                        json.dumps(anomaly_pattern),
                        primary_clause,
                        secondary_clauses,
                        severity_guidance,
                        explanation_template,
                    )

                successfully_seeded += 1
                logger.debug(f"Seeded CSM entry: {matrix_id}")

            except Exception as e:
                logger.error(f"Failed to seed CSM entry {entry.get('matrix_id')}: {e}")
                failed_entries.append(entry.get("matrix_id", "unknown"))

    logger.info(
        f"Completed CSM seeding: {successfully_seeded} successfully seeded, "
        f"{len(failed_entries)} failed"
    )

    if failed_entries:
        logger.warning(f"Failed CSM entries: {', '.join(failed_entries)}")


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
        await seed_csm(db_pool)
        logger.info("CSM seeding completed successfully")
    except Exception as e:
        logger.error(f"CSM seeding failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")


if __name__ == "__main__":
    asyncio.run(main())
