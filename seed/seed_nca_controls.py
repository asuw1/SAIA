"""Seed script for loading NCA controls into Qdrant."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.rag_service import RAGService
from backend.config import settings

logger = logging.getLogger(__name__)


async def seed_nca_controls() -> None:
    """
    Load NCA controls from JSON file, embed them, and upsert to Qdrant.

    Flow:
    1. Load nca_controls.json from seed directory
    2. For each control:
       - Extract full_text for embedding
       - Generate embedding via RAGService
       - Prepare metadata with control_id, domain, subdomain, title, keywords
       - Upsert to Qdrant nca_controls collection
    3. Log results
    """
    logger.info("Starting NCA controls seeding")

    # Initialize RAG service
    rag_service = RAGService(
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        embedding_model_name=settings.embedding_model,
    )

    # Ensure collections exist
    try:
        await rag_service.ensure_collections()
        logger.info("Ensured Qdrant collections exist")
    except Exception as e:
        logger.error(f"Failed to ensure collections: {e}")
        raise

    # Load controls from JSON file
    controls_path = Path(__file__).parent / "nca_controls.json"

    if not controls_path.exists():
        logger.error(f"Controls file not found: {controls_path}")
        raise FileNotFoundError(f"NCA controls file not found at {controls_path}")

    try:
        with open(controls_path, "r") as f:
            controls = json.load(f)
        logger.info(f"Loaded {len(controls)} controls from {controls_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse controls JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load controls file: {e}")
        raise

    # Upsert controls to Qdrant
    successfully_upserted = 0
    failed_controls = []

    for control in controls:
        try:
            control_id = control.get("control_id")
            full_text = control.get("full_text", "")
            domain = control.get("domain", "")
            subdomain = control.get("subdomain", "")
            title = control.get("title", "")
            keywords = control.get("keywords", [])

            if not control_id or not full_text:
                logger.warning(
                    f"Skipping control with missing id or text: {control_id}"
                )
                failed_controls.append(control_id)
                continue

            # Prepare metadata
            metadata = {
                "control_id": control_id,
                "domain": domain,
                "subdomain": subdomain,
                "title": title,
                "keywords": keywords,
            }

            # Upsert to Qdrant
            await rag_service.upsert_control(
                control_id=control_id,
                text=full_text,
                metadata=metadata,
            )

            successfully_upserted += 1
            logger.debug(f"Upserted control {control_id}: {title}")

        except Exception as e:
            logger.error(f"Failed to upsert control {control.get('control_id')}: {e}")
            failed_controls.append(control.get("control_id"))

    # Log results
    logger.info(
        f"Completed NCA controls seeding: {successfully_upserted} successfully "
        f"upserted, {len(failed_controls)} failed"
    )

    if failed_controls:
        logger.warning(f"Failed controls: {', '.join(failed_controls)}")

    if successfully_upserted == 0:
        logger.error("No controls were successfully upserted!")
        raise RuntimeError("NCA controls seeding failed - no controls upserted")


async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        await seed_nca_controls()
        logger.info("NCA controls seeding completed successfully")
    except Exception as e:
        logger.error(f"NCA controls seeding failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
