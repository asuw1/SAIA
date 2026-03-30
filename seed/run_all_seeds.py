"""Master seed script that runs all seeds in order."""

import argparse
import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings

logger = logging.getLogger(__name__)


async def run_seed_module(module_name: str, module_path: Path) -> bool:
    """
    Dynamically import and run a seed module's main function.

    Args:
        module_name: Name of the module (for logging)
        module_path: Path to the module file

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Starting {module_name}")

        # Dynamically import the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            logger.error(f"Failed to create module spec for {module_name}")
            return False

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Call the main function
        if hasattr(module, "main"):
            await module.main()
        else:
            logger.error(f"Module {module_name} has no main() function")
            return False

        logger.info(f"Completed {module_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to run {module_name}: {e}", exc_info=True)
        return False


async def main(skip_qdrant: bool = False) -> None:
    """
    Run all seed scripts in order.

    Flow:
    1. seed_lookup_tables (action_privileges, asset_registry)
    2. seed_csm (control_signal_matrix)
    3. seed_rules (starter rules)
    4. seed_nca_controls (if not --skip-qdrant)

    Args:
        skip_qdrant: If True, skip Qdrant-dependent seeding
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 70)
    logger.info("Starting SAIA V4 Seed Script - Master Runner")
    logger.info("=" * 70)
    logger.info(
        f"Database: {settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
    logger.info(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    logger.info(f"Skip Qdrant: {skip_qdrant}")
    logger.info("=" * 70)

    seed_dir = Path(__file__).parent
    seed_scripts = []
    results = {}

    # Define seed scripts to run in order
    seed_scripts.append(("seed_lookup_tables", seed_dir / "seed_lookup_tables.py"))
    seed_scripts.append(("seed_csm", seed_dir / "seed_csm.py"))
    seed_scripts.append(("seed_rules", seed_dir / "seed_rules.py"))

    if not skip_qdrant:
        seed_scripts.append(("seed_nca_controls", seed_dir / "seed_nca_controls.py"))

    # Run each seed script
    for script_name, script_path in seed_scripts:
        if not script_path.exists():
            logger.error(f"Seed script not found: {script_path}")
            results[script_name] = False
            continue

        success = await run_seed_module(script_name, script_path)
        results[script_name] = success

        # If a critical seed fails, consider stopping
        # For now, we continue to attempt all seeds
        if not success:
            logger.warning(f"{script_name} failed but continuing with other seeds")

    # Log final results
    logger.info("=" * 70)
    logger.info("Seed Execution Summary")
    logger.info("=" * 70)

    all_success = True
    for script_name, success in results.items():
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"  {script_name}: {status}")
        if not success:
            all_success = False

    logger.info("=" * 70)

    if all_success:
        logger.info("All seed scripts completed successfully!")
        sys.exit(0)
    else:
        logger.error("Some seed scripts failed!")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run all SAIA V4 seed scripts in order"
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant-dependent seeding (NCA controls)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main(skip_qdrant=args.skip_qdrant))
    except Exception as e:
        logger.error(f"Master seed script failed: {e}", exc_info=True)
        sys.exit(1)
