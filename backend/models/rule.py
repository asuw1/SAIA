"""Rule Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


class FieldCheck(BaseModel):
    """A single field check condition in a rule."""

    field: str = Field(..., description="Field name to check")
    operator: str = Field(
        ...,
        description="Operator: equals, contains, gt, lt, gte, lte, regex, etc.",
    )
    value: Any = Field(..., description="Value to compare against")


class AggregationCheck(BaseModel):
    """Aggregation-based check for rule conditions."""

    group_by: list[str] = Field(..., min_length=1, description="Fields to group by")
    window_minutes: int = Field(..., gt=0, description="Time window in minutes")
    count_threshold: int = Field(..., gt=0, description="Count threshold to trigger")


class RuleConditions(BaseModel):
    """Complete condition set for a rule."""

    field_checks: list[FieldCheck] = Field(
        default_factory=list,
        description="List of field checks (AND logic)",
    )
    aggregation: Optional[AggregationCheck] = None


class RuleCreate(BaseModel):
    """Request model for creating a rule."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    domain: str = Field(..., description="Domain/department this rule applies to")
    clause_reference: str = Field(
        ...,
        description="Regulatory clause reference (e.g., PCI-DSS 2.1)",
    )
    severity: str = Field(
        ...,
        description="Critical, High, Medium, or Low",
    )
    conditions: RuleConditions


class RuleUpdate(BaseModel):
    """Request model for updating a rule."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    severity: Optional[str] = Field(
        None,
        description="Critical, High, Medium, or Low",
    )
    conditions: Optional[RuleConditions] = None
    is_active: Optional[bool] = None


class RuleResponse(BaseModel):
    """Response model for a rule."""

    id: UUID
    name: str
    description: Optional[str] = None
    domain: str
    clause_reference: str
    severity: str
    conditions: RuleConditions
    is_active: bool
    version: str = "1.0"
    author_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleTestResult(BaseModel):
    """Response model for rule testing results."""

    matched_events: int = Field(..., ge=0, description="Number of events matching the rule")
    sample_matches: list[dict] = Field(
        default_factory=list,
        description="Sample matched event records",
    )
