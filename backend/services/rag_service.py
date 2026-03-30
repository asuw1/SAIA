"""RAG (Retrieval-Augmented Generation) service using Qdrant for SAIA V4."""

import logging
from typing import Optional, Any
from uuid import UUID
import asyncio

from ..config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """Vector search service using Qdrant."""

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model_name: str = "BAAI/bge-base-en-v1.5",
    ):
        """
        Initialize RAG service with Qdrant connection.

        Args:
            qdrant_host: Qdrant server hostname
            qdrant_port: Qdrant server port
            embedding_model_name: Name of the embedding model to use
        """
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.embedding_model_name = embedding_model_name

        # Lazy-loaded embeddings model
        self._embeddings = None
        self._qdrant_client = None

    def _get_embeddings(self):
        """Lazy load the embeddings model."""
        if self._embeddings is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    f"Loading embedding model: {self.embedding_model_name}"
                )
                self._embeddings = SentenceTransformer(self.embedding_model_name)
            except ImportError:
                logger.warning(
                    "sentence_transformers not available, using mock embeddings"
                )
                self._embeddings = None
        return self._embeddings

    def _get_qdrant_client(self):
        """Lazy load the Qdrant client."""
        if self._qdrant_client is None:
            try:
                from qdrant_client import QdrantClient

                self._qdrant_client = QdrantClient(
                    host=self.qdrant_host,
                    port=self.qdrant_port,
                )
                logger.info(
                    f"Connected to Qdrant at {self.qdrant_host}:{self.qdrant_port}"
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Qdrant: {e}")
                self._qdrant_client = None
        return self._qdrant_client

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = self._get_embeddings()

        if embeddings is not None:
            try:
                embedding = embeddings.encode(text, convert_to_tensor=False)
                return embedding.tolist()
            except Exception as e:
                logger.warning(f"Error generating embedding: {e}")
                return self._mock_embedding(text)
        else:
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str) -> list[float]:
        """
        Generate a mock embedding based on text hash.

        Args:
            text: Text to embed

        Returns:
            768-dimensional mock embedding vector
        """
        import hashlib

        # Create a deterministic seed from the text
        hash_obj = hashlib.sha256(text.encode())
        seed = int.from_bytes(hash_obj.digest()[:4], byteorder="big")

        # Generate 768-dimensional vector using seeded random
        import random

        random.seed(seed)
        embedding = [random.gauss(0, 0.1) for _ in range(768)]

        return embedding

    async def ensure_collections(self) -> None:
        """
        Create Qdrant collections if they don't exist.

        Creates:
        - nca_controls: Collection for NCA control documents (768-dim, cosine distance)
        - confirmed_alerts: Collection for confirmed alerts (768-dim, cosine distance)
        """
        client = self._get_qdrant_client()

        if client is None:
            logger.warning("Qdrant client not available, skipping collection setup")
            return

        try:
            from qdrant_client.models import Distance, VectorParams

            # Create nca_controls collection
            try:
                client.create_collection(
                    collection_name="nca_controls",
                    vectors_config=VectorParams(
                        size=settings.embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection: nca_controls")
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(f"Error creating nca_controls collection: {e}")

            # Create confirmed_alerts collection
            try:
                client.create_collection(
                    collection_name="confirmed_alerts",
                    vectors_config=VectorParams(
                        size=settings.embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection: confirmed_alerts")
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(
                        f"Error creating confirmed_alerts collection: {e}"
                    )

        except Exception as e:
            logger.warning(f"Failed to ensure Qdrant collections: {e}")

    async def search_controls(
        self, query: str, top_k: int = 3
    ) -> list[dict]:
        """
        Semantic search in NCA controls collection.

        Args:
            query: Search query text
            top_k: Number of top results to return

        Returns:
            List of matching control documents with scores
        """
        client = self._get_qdrant_client()

        if client is None:
            logger.warning("Qdrant client not available")
            return []

        try:
            embedding = self.embed_text(query)

            from qdrant_client.models import PointIdList

            results = client.search(
                collection_name="nca_controls",
                query_vector=embedding,
                limit=top_k,
            )

            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload or {},
                }
                for result in results
            ]

        except Exception as e:
            logger.warning(f"Error searching NCA controls: {e}")
            return []

    async def get_controls_by_ids(self, control_ids: list[str]) -> list[dict]:
        """
        Retrieve NCA controls by exact ID match.

        Args:
            control_ids: List of control IDs to retrieve

        Returns:
            List of matching controls with full payloads
        """
        client = self._get_qdrant_client()

        if client is None:
            logger.warning("Qdrant client not available")
            return []

        try:
            # Convert string IDs to integers if needed
            int_ids = []
            for cid in control_ids:
                try:
                    int_ids.append(int(cid))
                except ValueError:
                    # Use hash of string ID
                    int_ids.append(int(hash(cid)) & 0x7FFFFFFF)

            points = client.retrieve(
                collection_name="nca_controls",
                ids=int_ids,
            )

            return [
                {
                    "id": point.id,
                    "payload": point.payload or {},
                }
                for point in points
            ]

        except Exception as e:
            logger.warning(f"Error retrieving controls by ID: {e}")
            return []

    async def search_confirmed_alerts(
        self, query: str, top_k: int = 2
    ) -> list[dict]:
        """
        Semantic search in confirmed alerts collection.

        Args:
            query: Search query text
            top_k: Number of top results to return

        Returns:
            List of matching confirmed alerts with scores
        """
        client = self._get_qdrant_client()

        if client is None:
            logger.warning("Qdrant client not available")
            return []

        try:
            embedding = self.embed_text(query)

            results = client.search(
                collection_name="confirmed_alerts",
                query_vector=embedding,
                limit=top_k,
            )

            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload or {},
                }
                for result in results
            ]

        except Exception as e:
            logger.warning(f"Error searching confirmed alerts: {e}")
            return []

    async def upsert_confirmed_alert(
        self, alert_id: UUID | str, summary_text: str, payload: dict
    ) -> None:
        """
        Add or update a confirmed alert in the collection.

        Args:
            alert_id: UUID or unique identifier of the alert
            summary_text: Summary text to embed
            payload: Additional metadata to store
        """
        client = self._get_qdrant_client()

        if client is None:
            logger.warning("Qdrant client not available")
            return

        try:
            from qdrant_client.models import PointStruct

            # Convert alert_id to integer for Qdrant point ID
            if isinstance(alert_id, str):
                point_id = int(hash(alert_id)) & 0x7FFFFFFF
            else:
                point_id = int(hash(str(alert_id))) & 0x7FFFFFFF

            embedding = self.embed_text(summary_text)

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )

            client.upsert(
                collection_name="confirmed_alerts",
                points=[point],
            )

            logger.debug(f"Upserted confirmed alert {alert_id}")

        except Exception as e:
            logger.warning(f"Error upserting confirmed alert: {e}")

    async def upsert_control(
        self, control_id: str, text: str, metadata: dict
    ) -> None:
        """
        Add or update an NCA control in the collection.

        Args:
            control_id: Unique identifier for the control
            text: Control text to embed
            metadata: Additional metadata to store
        """
        client = self._get_qdrant_client()

        if client is None:
            logger.warning("Qdrant client not available")
            return

        try:
            from qdrant_client.models import PointStruct

            # Convert control_id to integer for Qdrant point ID
            point_id = int(hash(control_id)) & 0x7FFFFFFF

            embedding = self.embed_text(text)

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=metadata,
            )

            client.upsert(
                collection_name="nca_controls",
                points=[point],
            )

            logger.debug(f"Upserted control {control_id}")

        except Exception as e:
            logger.warning(f"Error upserting control: {e}")


# Global RAG service instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """
    Get or create the singleton RAG service.

    Returns:
        Global RAGService instance
    """
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(
            qdrant_host=settings.qdrant_host,
            qdrant_port=settings.qdrant_port,
            embedding_model_name=settings.embedding_model,
        )
    return _rag_service
