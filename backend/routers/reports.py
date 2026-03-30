"""Report generation router for SAIA V4."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user, require_roles
from ..models.base import Alert, Case, Report

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate compliance report",
    description="Generate compliance report (Admin, Compliance Officer only)",
)
async def generate_report(
    start_date: datetime = Query(..., description="Start date for report period"),
    end_date: datetime = Query(..., description="End date for report period"),
    domain: Optional[str] = Query(None),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> dict:
    """
    Generate a compliance report for specified period.

    Args:
        start_date: Report start date
        end_date: Report end date
        domain: Optional domain filter
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        Status message with report ID
    """
    if start_date >= end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    report_id = uuid4()

    filters = [
        Alert.created_at >= start_date,
        Alert.created_at <= end_date,
    ]

    if domain:
        filters.append(Alert.domain == domain)

    alerts_stmt = select(Alert).where(and_(*filters))
    alerts_result = await db.execute(alerts_stmt)
    alerts = alerts_result.scalars().all()

    report_data = {
        "report_id": str(report_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "domain": domain or "all",
        "summary": {
            "total_alerts": len(alerts),
            "critical": sum(1 for a in alerts if a.severity == "Critical"),
            "high": sum(1 for a in alerts if a.severity == "High"),
            "medium": sum(1 for a in alerts if a.severity == "Medium"),
            "low": sum(1 for a in alerts if a.severity == "Low"),
            "by_source": {
                "rule": sum(1 for a in alerts if a.source == "rule"),
                "ai": sum(1 for a in alerts if a.source == "ai"),
                "both": sum(1 for a in alerts if a.source == "both"),
            },
            "by_status": {
                "open": sum(1 for a in alerts if a.status == "open"),
                "investigating": sum(1 for a in alerts if a.status == "investigating"),
                "resolved": sum(1 for a in alerts if a.status == "resolved"),
                "verified": sum(1 for a in alerts if a.status == "verified"),
            },
            "resolved_cases": sum(1 for a in alerts if a.status == "resolved"),
            "verified_cases": sum(1 for a in alerts if a.status == "verified"),
        },
        "alerts_by_clause": {},
    }

    for alert in alerts:
        clause = alert.clause_reference or "unknown"
        if clause not in report_data["alerts_by_clause"]:
            report_data["alerts_by_clause"][clause] = {
                "count": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }

        report_data["alerts_by_clause"][clause]["count"] += 1
        report_data["alerts_by_clause"][clause][alert.severity.lower()] += 1

    new_report = Report(
        id=report_id,
        user_id=current_user.get("user_id"),
        title=f"Compliance Report {start_date.date()} to {end_date.date()}",
        report_type="compliance",
        content=report_data,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )

    db.add(new_report)
    await db.commit()

    return {
        "status": "generating",
        "report_id": str(report_id),
        "message": "Report queued for generation",
    }


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List reports",
    description="Get list of generated reports",
)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    report_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    List generated reports.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        report_type: Filter by report type
        db: Database session
        current_user: Current authenticated user

    Returns:
        Paginated list of reports
    """
    offset = (page - 1) * page_size

    filters = []
    if report_type:
        filters.append(Report.report_type == report_type)

    count_stmt = select(func.count(Report.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = select(Report)
    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(Report.created_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    reports = result.scalars().all()

    return {
        "reports": [
            {
                "id": str(r.id),
                "title": r.title,
                "report_type": r.report_type,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{report_id}",
    status_code=status.HTTP_200_OK,
    summary="Get report content",
    description="Retrieve full report content",
)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Get report content.

    Args:
        report_id: Report ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Report object with full content

    Raises:
        HTTPException: 404 if report not found
    """
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalars().first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return {
        "id": str(report.id),
        "title": report.title,
        "report_type": report.report_type,
        "status": report.status,
        "created_at": report.created_at.isoformat(),
        "content": report.content,
    }
