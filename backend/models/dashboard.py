"""Dashboard Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field
from typing import Optional


class KPIResponse(BaseModel):
    """Response model for dashboard KPIs."""

    active_alerts: int = Field(..., ge=0)
    resolved_cases_30d: int = Field(..., ge=0)
    pending_reports: int = Field(..., ge=0)
    avg_response_time_hours: float = Field(..., ge=0.0)
    data_quality_score: float = Field(..., ge=0.0, le=1.0)


class AnomalyBucket(BaseModel):
    """Single bucket in anomaly score distribution."""

    range_start: float = Field(..., ge=0.0, le=1.0)
    range_end: float = Field(..., ge=0.0, le=1.0)
    count: int = Field(..., ge=0)


class AnomalyDistributionResponse(BaseModel):
    """Response model for anomaly score distribution."""

    buckets: list[AnomalyBucket]
    threshold: float = Field(..., ge=0.0, le=1.0)
    total_events: int = Field(..., ge=0)
    flagged_events: int = Field(..., ge=0)


class PrecisionDataPoint(BaseModel):
    """Single data point in precision tracking."""

    date: str = Field(..., description="ISO date string")
    precision: float = Field(..., ge=0.0, le=1.0)
    tp_count: int = Field(..., ge=0, description="True positive count")
    fp_count: int = Field(..., ge=0, description="False positive count")
    domain: str


class PrecisionTrackerResponse(BaseModel):
    """Response model for precision tracking over time."""

    data_points: list[PrecisionDataPoint]
    overall_precision: float = Field(..., ge=0.0, le=1.0)
    target_precision: float = Field(..., ge=0.0, le=1.0)
    total_tp: int = Field(..., ge=0)
    total_fp: int = Field(..., ge=0)


class DriftAlert(BaseModel):
    """Alert for model drift detection."""

    entity: str = Field(..., description="Entity experiencing drift (e.g., user, asset)")
    domain: str
    drift_metric: str = Field(..., description="Metric showing drift")
    shift_sigma: float = Field(..., description="Standard deviations from baseline")


class FeedbackSummary(BaseModel):
    """Summary of analyst feedback."""

    tp: int = Field(..., ge=0, description="True positive count")
    fp: int = Field(..., ge=0, description="False positive count")
    precision: float = Field(..., ge=0.0, le=1.0)


class ModelHealthResponse(BaseModel):
    """Response model for overall model health metrics."""

    events_processed_24h: int = Field(..., ge=0)
    events_flagged_24h: int = Field(..., ge=0)
    events_quarantined_24h: int = Field(..., ge=0)
    llm_queue_depth: int = Field(..., ge=0)
    llm_avg_latency_ms: float = Field(..., ge=0.0)
    active_baselines: int = Field(..., ge=0)
    drift_alerts: list[DriftAlert] = Field(default_factory=list)
    feedback_this_month: FeedbackSummary
