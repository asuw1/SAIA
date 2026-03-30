from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class LogEventOut(BaseModel):
    id:            int
    timestamp:     datetime
    source:        str
    event_type:    str
    principal:     Optional[str]
    action:        Optional[str]
    resource:      Optional[str]
    result:        Optional[str]
    source_ip:     Optional[str]
    asset_id:      Optional[str]
    session_id:    Optional[str]
    domain:        Optional[str]
    anomaly_score: Optional[float]
    is_quarantined: bool
    ingested_at:   datetime
    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    total_received:   int
    normalized:       int
    quarantined:      int
    alerts_triggered: int
    message:          str
