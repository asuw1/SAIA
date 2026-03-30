"""Log event Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class LogEventBase(BaseModel):
    """Base log event fields shared across schemas."""

    timestamp: datetime
    source: str = Field(..., description="vpn_server, firewall, app, cloud, etc.")
    event_type: str = Field(..., description="authentication, network, api_request, etc.")
    principal: Optional[str] = Field(None, description="User or service actor identifier")
    action: Optional[str] = Field(None, description="login_attempt, transfer, access, etc.")
    resource: Optional[str] = Field(None, description="vpn_gateway, endpoint, bucket, etc.")
    result: Optional[str] = Field(None, description="success, failed, blocked, etc.")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    asset_id: Optional[str] = Field(None, description="Human-readable asset identifier")
    domain: Optional[str] = Field(None, description="Department/business unit for RBAC scoping")
    raw_log: dict = Field(default_factory=dict, description="Raw log data as dictionary")


class LogEventCreate(LogEventBase):
    """Request model for creating log events."""

    pass


class LogEventResponse(LogEventBase):
    """Response model for log events."""

    id: UUID
    upload_id: Optional[UUID] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_quarantined: bool = False
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_flagged: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("quality_score", mode="before")
    @classmethod
    def convert_quality_score(cls, v: Optional[str | float]) -> Optional[float]:
        """Convert string quality score to float."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v

    @field_validator("anomaly_score", mode="before")
    @classmethod
    def convert_anomaly_score(cls, v: Optional[str | float]) -> Optional[float]:
        """Convert string anomaly score to float."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v


class LogUploadResponse(BaseModel):
    """Response model for a batch log upload."""

    upload_id: UUID
    events_parsed: int = Field(..., ge=0)
    events_accepted: int = Field(..., ge=0)
    events_quarantined: int = Field(..., ge=0)


class LogIngestRequest(BaseModel):
    """Request model for ingesting logs from a source."""

    source_name: str = Field(..., min_length=1, description="Name of the log source")
    domain: str = Field(..., min_length=1, description="Domain/department identifier")
    events: list[dict] = Field(..., description="List of raw log events to ingest")


class UploadResponse(BaseModel):
    """Response model for a completed log upload."""

    id: UUID
    user_id: UUID
    source_name: str
    domain: str
    filename: str
    events_parsed: int = Field(..., ge=0)
    events_accepted: int = Field(..., ge=0)
    events_quarantined: int = Field(..., ge=0)
    status: str = Field(..., description="completed, in_progress, failed, etc.")
    created_at: datetime

    model_config = {"from_attributes": True}
