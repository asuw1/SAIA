"""Alert Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from uuid import UUID
from datetime import datetime


class TopFeature(BaseModel):
    """Top anomaly feature contributing to an alert."""

    name: str = Field(..., description="Feature name")
    value: Any = Field(..., description="Feature value")
    deviation_sigma: Optional[float] = Field(
        None,
        description="Standard deviations from baseline",
    )


class TriggeredRule(BaseModel):
    """Rule that was triggered for an alert."""

    rule_id: UUID
    rule_name: str
    clause: str


class LLMAssessment(BaseModel):
    """LLM-powered assessment of an alert."""

    violation_detected: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    primary_clause: str
    secondary_clauses: list[str] = Field(default_factory=list)
    severity_assessment: str = Field(
        ...,
        description="Critical, High, Medium, or Low",
    )
    reasoning: str
    recommended_action: str
    false_positive_likelihood: float = Field(..., ge=0.0, le=1.0)


class AlertResponse(BaseModel):
    """Response model for an alert."""

    id: UUID
    alert_number: int
    domain: str
    severity: str = Field(..., description="Critical, High, Medium, or Low")
    status: str = Field(
        ...,
        description="open, investigating, resolved, or verified",
    )
    source: str = Field(
        ...,
        description="rule, ai, or both",
    )
    entity_principal: Optional[str] = None
    clause_reference: str
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_features: list[TopFeature] = Field(default_factory=list)
    triggered_rules: list[TriggeredRule] = Field(default_factory=list)
    llm_assessment: Optional[LLMAssessment] = None
    event_count: int = Field(default=0, ge=0)
    assigned_to: Optional[UUID] = None
    case_id: Optional[UUID] = None
    analyst_verdict: Optional[str] = Field(
        None,
        description="true_positive or false_positive",
    )
    analyst_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    """Request model for updating an alert."""

    status: Optional[str] = Field(
        None,
        description="open, investigating, resolved, or verified",
    )
    assigned_to: Optional[UUID] = None
    analyst_comment: Optional[str] = None


class AlertFeedback(BaseModel):
    """Request model for providing feedback on an alert."""

    verdict: Literal["true_positive", "false_positive"]
    comment: str


class AlertListResponse(BaseModel):
    """Response model for paginated alert list."""

    alerts: list[AlertResponse]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
