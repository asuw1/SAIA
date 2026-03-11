"""
Alert Service
Shared between Pair 1 and Pair 2.
Handles alert retrieval, status updates, comments, and case grouping.
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.alert import Alert
from models.case import Case, AlertComment
from schemas.alert import AlertUpdate, CommentCreate, CaseCreate
from datetime import datetime, timezone
from typing import Optional


def get_alerts(
    db: Session,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Alert]:
    query = db.query(Alert).order_by(desc(Alert.detected_at))
    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)
    return query.offset(offset).limit(limit).all()


def get_alert_by_id(alert_id: int, db: Session) -> Optional[Alert]:
    return db.query(Alert).filter(Alert.id == alert_id).first()


def update_alert(alert_id: int, data: AlertUpdate, db: Session) -> Optional[Alert]:
    alert = get_alert_by_id(alert_id, db)
    if not alert:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    if data.status == "resolved":
        alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


def add_comment(alert_id: int, user_id: int, data: CommentCreate, db: Session) -> AlertComment:
    comment = AlertComment(alert_id=alert_id, user_id=user_id, content=data.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def create_case(data: CaseCreate, user_id: int, db: Session) -> Case:
    """Group a set of alerts into a new case."""
    case = Case(title=data.title, description=data.description, assigned_to=user_id)
    db.add(case)
    db.flush()

    alerts = db.query(Alert).filter(Alert.id.in_(data.alert_ids)).all()
    for alert in alerts:
        alert.case_id = case.id

    db.commit()
    db.refresh(case)
    return case


def get_alert_summary(db: Session) -> dict:
    """KPI summary counts used by the dashboard."""
    total    = db.query(Alert).count()
    critical = db.query(Alert).filter(Alert.severity == "Critical", Alert.status != "resolved").count()
    high     = db.query(Alert).filter(Alert.severity == "High",     Alert.status != "resolved").count()
    medium   = db.query(Alert).filter(Alert.severity == "Medium",   Alert.status != "resolved").count()
    overdue  = db.query(Alert).filter(Alert.is_overdue == True).count()
    resolved = db.query(Alert).filter(Alert.status == "resolved").count()

    return {
        "total": total,
        "critical": critical,
        "high": high,
        "medium": medium,
        "overdue": overdue,
        "resolved": resolved,
    }
