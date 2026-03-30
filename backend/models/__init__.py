"""Pydantic models and schemas for SAIA V4.

This module contains all request/response validation schemas for the SAIA V4 backend.
These are pure Pydantic models for API input/output validation, not SQLAlchemy ORM models.
"""

# Auth schemas
from .auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    TokenPayload,
)

# Log event schemas
from .log_event import (
    LogEventBase,
    LogEventCreate,
    LogEventResponse,
    LogUploadResponse,
    LogIngestRequest,
    UploadResponse,
)

# Alert schemas
from .alert import (
    TopFeature,
    TriggeredRule,
    LLMAssessment,
    AlertResponse,
    AlertUpdate,
    AlertFeedback,
    AlertListResponse,
)

# Rule schemas
from .rule import (
    FieldCheck,
    AggregationCheck,
    RuleConditions,
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleTestResult,
)

# Case schemas
from .case import (
    CaseCreate,
    CaseUpdate,
    NarrativeResponse,
    CaseResponse,
    EvidenceGenerateResponse,
)

# Chat schemas
from .chat import (
    ChatMessage,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatHistoryResponse,
)

# Dashboard schemas
from .dashboard import (
    KPIResponse,
    AnomalyBucket,
    AnomalyDistributionResponse,
    PrecisionDataPoint,
    PrecisionTrackerResponse,
    DriftAlert,
    FeedbackSummary,
    ModelHealthResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "UserResponse",
    "TokenPayload",
    # Log events
    "LogEventBase",
    "LogEventCreate",
    "LogEventResponse",
    "LogUploadResponse",
    "LogIngestRequest",
    "UploadResponse",
    # Alerts
    "TopFeature",
    "TriggeredRule",
    "LLMAssessment",
    "AlertResponse",
    "AlertUpdate",
    "AlertFeedback",
    "AlertListResponse",
    # Rules
    "FieldCheck",
    "AggregationCheck",
    "RuleConditions",
    "RuleCreate",
    "RuleUpdate",
    "RuleResponse",
    "RuleTestResult",
    # Cases
    "CaseCreate",
    "CaseUpdate",
    "NarrativeResponse",
    "CaseResponse",
    "EvidenceGenerateResponse",
    # Chat
    "ChatMessage",
    "ChatMessageResponse",
    "ChatSessionResponse",
    "ChatHistoryResponse",
    # Dashboard
    "KPIResponse",
    "AnomalyBucket",
    "AnomalyDistributionResponse",
    "PrecisionDataPoint",
    "PrecisionTrackerResponse",
    "DriftAlert",
    "FeedbackSummary",
    "ModelHealthResponse",
]
