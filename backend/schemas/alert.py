from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    severity: str
    status: str
    source: str
    clause_id: int
    rule_id: Optional[int]
    log_event_id: Optional[int]
    assigned_to: Optional[int]
    case_id: Optional[int]
    detected_at: datetime
    sla_deadline: Optional[datetime]
    is_overdue: bool
    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[int] = None
    case_id: Optional[int] = None


class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    alert_id: int
    user_id: int
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Case ─────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    alert_ids: list[int]                   # alerts to group into this case


class CaseOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    assigned_to: Optional[int]
    sla_deadline: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}
