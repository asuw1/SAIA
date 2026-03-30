"""LLM queue worker for processing enrichment requests in SAIA V4."""

import asyncio
import logging
from uuid import UUID

import asyncpg

from ..config import settings
from ..services.enrichment_service import enrich_alert
from ..services.llm_client import LLMClient
from ..services.rag_service import RAGService

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


async def process_queue(
    db_pool: asyncpg.pool.Pool,
    llm_client: LLMClient,
    rag_service: RAGService,
) -> int:
    """
    Pick top 5 pending items by priority from llm_queue and process each.

    Flow:
    1. Query llm_queue for pending items sorted by priority DESC, limit 5
    2. For each item:
       - Mark as 'processing'
       - Call enrichment_service.enrich_alert()
       - Mark as 'done' on success
       - Mark as 'failed' on error, increment attempts
       - Skip if attempts >= 3

    Args:
        db_pool: AsyncPG connection pool
        llm_client: LLM client instance
        rag_service: RAG service instance

    Returns:
        Number of items processed
    """
    processed_count = 0

    async with db_pool.acquire() as db:
        try:
            # Get top 5 pending items by priority, excluding those with too many attempts
            pending_items = await db.fetch(
                """
                SELECT id, alert_id, priority, attempts
                FROM llm_queue
                WHERE status = 'pending' AND attempts < 3
                ORDER BY priority DESC, created_at ASC
                LIMIT 5
                """,
            )

            logger.info(f"Found {len(pending_items)} pending items to process")

            for item in pending_items:
                item_id = item["id"]
                alert_id = UUID(item["alert_id"])
                attempts = item["attempts"]

                try:
                    # Mark as processing
                    await db.execute(
                        """
                        UPDATE llm_queue
                        SET status = 'processing', updated_at = NOW()
                        WHERE id = $1
                        """,
                        item_id,
                    )

                    logger.info(
                        f"Processing LLM queue item {item_id} for alert {alert_id} "
                        f"(attempt {attempts + 1}/3)"
                    )

                    # Process the enrichment
                    await enrich_alert(db, alert_id, rag_service, llm_client)

                    # Mark as done
                    await db.execute(
                        """
                        UPDATE llm_queue
                        SET status = 'done', updated_at = NOW()
                        WHERE id = $1
                        """,
                        item_id,
                    )

                    logger.info(f"Successfully completed processing for item {item_id}")
                    processed_count += 1

                except Exception as e:
                    # Increment attempts and decide status
                    new_attempts = attempts + 1

                    if new_attempts >= 3:
                        # Mark as failed after 3 attempts
                        status = "failed"
                        logger.error(
                            f"Item {item_id} failed after 3 attempts: {str(e)}"
                        )
                    else:
                        # Mark as retrying
                        status = "retrying"
                        logger.warning(
                            f"Item {item_id} failed (attempt {new_attempts}/3), "
                            f"will retry: {str(e)}"
                        )

                    await db.execute(
                        """
                        UPDATE llm_queue
                        SET status = $1, attempts = $2, updated_at = NOW()
                        WHERE id = $3
                        """,
                        status,
                        new_attempts,
                        item_id,
                    )

        except Exception as e:
            logger.error(f"Error querying pending items: {str(e)}")

    return processed_count


async def run_worker(interval_seconds: int = 120) -> None:
    """
    Main worker loop that processes the queue at regular intervals.

    Flow:
    1. Initialize connections (DB pool, LLM client, RAG service)
    2. Loop forever:
       - Sleep for interval_seconds
       - Call process_queue()
       - Log results

    Args:
        interval_seconds: Interval in seconds between queue processing cycles (default 120)
    """
    logger.info(
        f"Starting LLM queue worker with {interval_seconds}s interval"
    )

    # Initialize connections
    try:
        db_pool = await get_db_pool()
        logger.info("Connected to database")
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        return

    llm_client = LLMClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        mock_mode=settings.llm_mock_mode,
    )
    logger.info(
        f"Initialized LLM client (model: {settings.llm_model}, "
        f"mock_mode: {settings.llm_mock_mode})"
    )

    rag_service = RAGService(
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        embedding_model_name=settings.embedding_model,
    )
    logger.info(
        f"Initialized RAG service (Qdrant: {settings.qdrant_host}:{settings.qdrant_port})"
    )

    # Ensure Qdrant collections exist
    try:
        await rag_service.ensure_collections()
        logger.info("Ensured Qdrant collections are created")
    except Exception as e:
        logger.warning(f"Failed to ensure Qdrant collections: {e}")

    try:
        while True:
            try:
                # Sleep first, then process
                logger.debug(f"Sleeping for {interval_seconds}s before next cycle")
                await asyncio.sleep(interval_seconds)

                # Process queue
                processed_count = await process_queue(db_pool, llm_client, rag_service)
                logger.info(f"Processed {processed_count} items in this cycle")

            except Exception as e:
                logger.error(f"Error in worker cycle: {e}", exc_info=True)
                # Continue the loop even on error
                await asyncio.sleep(interval_seconds)

    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    finally:
        await db_pool.close()
        logger.info("LLM queue worker stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        asyncio.run(run_worker(interval_seconds=120))
    except Exception as e:
        logger.error(f"Worker failed to start: {e}", exc_info=True)
