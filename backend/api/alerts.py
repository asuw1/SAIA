from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.user import User
from schemas.alert import AlertOut, AlertUpdate, CommentCreate, CommentOut, CaseCreate, CaseOut
from services.alert_service import (
    get_alerts, get_alert_by_id, update_alert,
    add_comment, create_case, get_alert_summary
)
from core.dependencies import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Dashboard KPI counts."""
    return get_alert_summary(db)


@router.get("/", response_model=list[AlertOut])
def list_alerts(
    severity: Optional[str] = None,
    status:   Optional[str] = None,
    limit:    int = 100,
    offset:   int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return get_alerts(db, severity, status, limit, offset)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    alert = get_alert_by_id(alert_id, db)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertOut)
def patch_alert(
    alert_id: int,
    data: AlertUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = update_alert(alert_id, data, db)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/comments", response_model=CommentOut)
def post_comment(
    alert_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return add_comment(alert_id, current_user.id, data, db)


@router.post("/cases", response_model=CaseOut)
def new_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_case(data, current_user.id, db)
