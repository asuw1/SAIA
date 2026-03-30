"""Case Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CaseCreate(BaseModel):
    """Request model for creating a case."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    severity: str = Field(
        ...,
        description="Critical, High, Medium, or Low",
    )
    alert_ids: list[UUID] = Field(
        default_factory=list,
        description="Related alert IDs",
    )


class CaseUpdate(BaseModel):
    """Request model for updating a case."""

    status: Optional[str] = Field(
        None,
        description="open, in_progress, resolved, or verified",
    )
    assigned_to: Optional[UUID] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class NarrativeResponse(BaseModel):
    """Response model for case narrative."""

    narrative_draft: Optional[str] = None
    narrative_status: str = Field(
        ...,
        description="draft, submitted, or approved",
    )
    narrative_approved: bool


class CaseResponse(BaseModel):
    """Response model for a case."""

    id: UUID
    case_number: int
    title: str
    description: Optional[str] = None
    status: str = Field(
        ...,
        description="open, in_progress, resolved, or verified",
    )
    severity: str = Field(..., description="Critical, High, Medium, or Low")
    assigned_to: Optional[UUID] = None
    narrative_draft: Optional[str] = None
    narrative_approved: bool = False
    narrative_approved_by: Optional[UUID] = None
    narrative_approved_at: Optional[datetime] = None
    narrative_status: str = Field(
        default="draft",
        description="draft, submitted, or approved",
    )
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    alert_count: int = Field(default=0, ge=0)

    model_config = {"from_attributes": True}


class EvidenceGenerateResponse(BaseModel):
    """Response model for evidence generation request."""

    case_id: UUID
    status: str = Field(
        ...,
        description="pending, in_progress, completed, or failed",
    )
    message: str
