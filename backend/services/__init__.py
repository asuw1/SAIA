"""Business logic services for SAIA V4."""

from .websocket import ConnectionManager
from .llm_client import LLMClient, get_llm_client
from .rag_service import RAGService, get_rag_service
from .ingestion import (
    compute_quality_score,
    normalize_event,
    parse_json_upload,
    parse_csv_upload,
    process_upload,
    process_ingest,
)
from .feature_extractor import extract_features, FEATURE_NAMES
from .ml_detector import (
    load_models,
    normalize_if_score,
    compute_combined_score,
    compute_severity,
    detect_anomaly,
    update_entity_baselines,
)

__all__ = [
    "ConnectionManager",
    "LLMClient",
    "get_llm_client",
    "RAGService",
    "get_rag_service",
    "compute_quality_score",
    "normalize_event",
    "parse_json_upload",
    "parse_csv_upload",
    "process_upload",
    "process_ingest",
    "extract_features",
    "FEATURE_NAMES",
    "load_models",
    "normalize_if_score",
    "compute_combined_score",
    "compute_severity",
    "detect_anomaly",
    "update_entity_baselines",
]
