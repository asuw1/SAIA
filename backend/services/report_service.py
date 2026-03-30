"""
Report Service
Pair 2 (Rakan + Faisal) — responsible for this module.

Queries alerts and log events for a given date range and framework,
then builds a compliance report record.
PDF/CSV export can be added here in Phase 2.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.report import Report
from models.alert import Alert
from models.log_event import LogEvent
from models.clause import Clause
from schemas.report import ReportRequest
from datetime import datetime, timezone


def generate_report(data: ReportRequest, user_id: int, db: Session) -> Report:
    """
    Build a compliance report for the requested framework and date range.
    """
    # Count log events in the date range
    events_q = db.query(LogEvent).filter(
        and_(LogEvent.timestamp >= data.date_from, LogEvent.timestamp <= data.date_to)
    )
    events_count = events_q.count()

    # Count violations (alerts) mapped to the requested framework
    alerts_q = db.query(Alert).join(Clause).filter(
        and_(
            Alert.detected_at >= data.date_from,
            Alert.detected_at <= data.date_to,
        )
    )
    if data.framework != "ALL":
        alerts_q = alerts_q.filter(Clause.framework == data.framework)

    violations_count = alerts_q.count()

    report = Report(
        title            = data.title,
        framework        = data.framework,
        date_from        = data.date_from,
        date_to          = data.date_to,
        export_format    = data.export_format,
        events_count     = events_count,
        violations_count = violations_count,
        generated_by     = user_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, limit: int = 20) -> list[Report]:
    return db.query(Report).order_by(Report.created_at.desc()).limit(limit).all()
