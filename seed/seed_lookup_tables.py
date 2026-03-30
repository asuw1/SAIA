"""Seed script for loading action privileges and asset registry."""

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


async def seed_action_privileges(db_pool: asyncpg.pool.Pool) -> int:
    """
    Load action privilege mappings from JSON file.

    Args:
        db_pool: AsyncPG connection pool

    Returns:
        Number of successfully seeded action privileges
    """
    logger.info("Starting action privileges seeding")

    # Load action privileges from JSON file
    privileges_path = Path(__file__).parent / "action_privileges.json"

    if not privileges_path.exists():
        logger.error(f"Action privileges file not found: {privileges_path}")
        raise FileNotFoundError(f"Action privileges file not found at {privileges_path}")

    try:
        with open(privileges_path, "r") as f:
            privileges = json.load(f)
        logger.info(f"Loaded {len(privileges)} action privileges from {privileges_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse action privileges JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load action privileges file: {e}")
        raise

    # Upsert privileges to database
    async with db_pool.acquire() as db:
        successfully_seeded = 0
        failed_actions = []

        for privilege in privileges:
            try:
                action = privilege.get("action")
                privilege_level = privilege.get("privilege_level")

                if not action or privilege_level is None:
                    logger.warning(
                        f"Skipping privilege with missing action or level: {privilege}"
                    )
                    failed_actions.append(action or "unknown")
                    continue

                # Check if action already exists
                existing = await db.fetchval(
                    """
                    SELECT privilege_level FROM action_privilege_levels WHERE action = $1
                    """,
                    action,
                )

                if existing is not None:
                    logger.debug(f"Action privilege '{action}' already exists, skipping")
                    continue

                # Insert new action privilege
                await db.execute(
                    """
                    INSERT INTO action_privilege_levels (action, privilege_level)
                    VALUES ($1, $2)
                    """,
                    action,
                    privilege_level,
                )

                successfully_seeded += 1
                logger.debug(f"Seeded action privilege: {action} -> level {privilege_level}")

            except Exception as e:
                logger.error(f"Failed to seed action privilege {privilege.get('action')}: {e}")
                failed_actions.append(privilege.get("action", "unknown"))

    logger.info(
        f"Completed action privileges seeding: {successfully_seeded} successfully seeded, "
        f"{len(failed_actions)} failed"
    )

    if failed_actions:
        logger.warning(f"Failed actions: {', '.join(failed_actions)}")

    return successfully_seeded


async def seed_asset_registry(db_pool: asyncpg.pool.Pool) -> int:
    """
    Load asset registry entries from JSON file.

    Args:
        db_pool: AsyncPG connection pool

    Returns:
        Number of successfully seeded assets
    """
    logger.info("Starting asset registry seeding")

    # Load assets from JSON file
    assets_path = Path(__file__).parent / "asset_registry.json"

    if not assets_path.exists():
        logger.error(f"Asset registry file not found: {assets_path}")
        raise FileNotFoundError(f"Asset registry file not found at {assets_path}")

    try:
        with open(assets_path, "r") as f:
            assets = json.load(f)
        logger.info(f"Loaded {len(assets)} assets from {assets_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse asset registry JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load asset registry file: {e}")
        raise

    # Upsert assets to database
    async with db_pool.acquire() as db:
        successfully_seeded = 0
        failed_assets = []

        for asset in assets:
            try:
                asset_name = asset.get("asset_name")
                criticality_score = asset.get("criticality_score")
                is_sensitive = asset.get("is_sensitive", False)

                if not asset_name or criticality_score is None:
                    logger.warning(
                        f"Skipping asset with missing name or criticality: {asset}"
                    )
                    failed_assets.append(asset_name or "unknown")
                    continue

                # Check if asset already exists by name
                existing = await db.fetchval(
                    """
                    SELECT asset_id FROM asset_registry WHERE asset_name = $1
                    """,
                    asset_name,
                )

                if existing:
                    logger.debug(f"Asset '{asset_name}' already exists, skipping")
                    continue

                # Insert new asset
                asset_id = str(uuid4())
                await db.execute(
                    """
                    INSERT INTO asset_registry
                    (asset_id, asset_name, criticality_score, is_sensitive)
                    VALUES ($1, $2, $3, $4)
                    """,
                    asset_id,
                    asset_name,
                    criticality_score,
                    is_sensitive,
                )

                successfully_seeded += 1
                logger.debug(
                    f"Seeded asset: {asset_name} (criticality {criticality_score}, "
                    f"sensitive={is_sensitive})"
                )

            except Exception as e:
                logger.error(f"Failed to seed asset {asset.get('asset_name')}: {e}")
                failed_assets.append(asset.get("asset_name", "unknown"))

    logger.info(
        f"Completed asset registry seeding: {successfully_seeded} successfully seeded, "
        f"{len(failed_assets)} failed"
    )

    if failed_assets:
        logger.warning(f"Failed assets: {', '.join(failed_assets)}")

    return successfully_seeded


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

        privileges_count = await seed_action_privileges(db_pool)
        assets_count = await seed_asset_registry(db_pool)

        logger.info(
            f"Lookup tables seeding completed: {privileges_count} action privileges, "
            f"{assets_count} assets"
        )
    except Exception as e:
        logger.error(f"Lookup tables seeding failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")


if __name__ == "__main__":
    asyncio.run(main())
