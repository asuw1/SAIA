"""Alert management router for SAIA V4."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user, require_roles
from ..models.alert import (
    AlertResponse,
    AlertListResponse,
    AlertUpdate,
    AlertFeedback,
)
from ..models.base import Alert, LogEvent
from ..services.feedback import submit_feedback
from ..services.rag_service import RAGService

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


@router.get(
    "",
    response_model=AlertListResponse,
    status_code=status.HTTP_200_OK,
    summary="List alerts",
    description="Get paginated alerts with filters",
)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    domain: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AlertListResponse:
    """
    List alerts with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        severity: Filter by severity (Critical, High, Medium, Low)
        status_filter: Filter by status (open, investigating, resolved, verified)
        domain: Filter by domain
        source: Filter by source (rule, ai, both)
        db: Database session
        current_user: Current authenticated user

    Returns:
        AlertListResponse with paginated alerts
    """
    user_data_scope = current_user.get("data_scope", ["*"])
    user_id = current_user.get("user_id")
    user_role = current_user.get("role")
    offset = (page - 1) * page_size

    filters = []

    if user_data_scope != ["*"]:
        filters.append(Alert.domain.in_(user_data_scope))

    if user_role == "Analyst":
        filters.append(Alert.assigned_to == user_id)

    if severity:
        filters.append(Alert.severity == severity)

    if status_filter:
        filters.append(Alert.status == status_filter)

    if domain:
        filters.append(Alert.domain == domain)

    if source:
        filters.append(Alert.source == source)

    count_stmt = select(func.count(Alert.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = select(Alert)
    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(Alert.created_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    alerts = result.scalars().all()

    alert_responses = []
    for alert in alerts:
        event_count_stmt = select(func.count(LogEvent.id)).where(
            LogEvent.id.in_([alert.event_ids] if alert.event_ids else [])
        )
        event_count_result = await db.execute(event_count_stmt)
        event_count = event_count_result.scalar() or 0

        alert_dict = AlertResponse.model_validate(alert).model_dump()
        alert_dict["event_count"] = event_count
        alert_responses.append(AlertResponse(**alert_dict))

    return AlertListResponse(
        alerts=alert_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    status_code=status.HTTP_200_OK,
    summary="Get alert details",
    description="Get full alert details including triggered rules",
)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AlertResponse:
    """
    Get detailed information for a specific alert.

    Args:
        alert_id: Alert ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AlertResponse with full details

    Raises:
        HTTPException: 404 if alert not found, 403 if user lacks access
    """
    user_data_scope = current_user.get("data_scope", ["*"])

    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalars().first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if user_data_scope != ["*"] and alert.domain not in user_data_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this alert",
        )

    event_count_stmt = select(func.count(LogEvent.id)).where(
        LogEvent.id.in_([alert.event_ids] if alert.event_ids else [])
    )
    event_count_result = await db.execute(event_count_stmt)
    event_count = event_count_result.scalar() or 0

    alert_dict = AlertResponse.model_validate(alert).model_dump()
    alert_dict["event_count"] = event_count

    return AlertResponse(**alert_dict)


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    status_code=status.HTTP_200_OK,
    summary="Update alert",
    description="Update alert status, assignment, or comments",
)
async def update_alert(
    alert_id: UUID,
    update_data: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AlertResponse:
    """
    Update alert properties.

    Args:
        alert_id: Alert ID
        update_data: Fields to update
        db: Database session
        current_user: Current authenticated user

    Returns:
        AlertResponse with updated data

    Raises:
        HTTPException: 404 if alert not found, 403 if user lacks access
    """
    user_data_scope = current_user.get("data_scope", ["*"])

    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalars().first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if user_data_scope != ["*"] and alert.domain not in user_data_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this alert",
        )

    update_dict = update_data.model_dump(exclude_unset=True)

    if "status" in update_dict:
        alert.status = update_dict["status"]

    if "assigned_to" in update_dict:
        alert.assigned_to = update_dict["assigned_to"]

    if "analyst_comment" in update_dict:
        alert.analyst_comment = update_dict["analyst_comment"]

    alert.updated_at = datetime.now(timezone.utc)

    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    event_count_stmt = select(func.count(LogEvent.id)).where(
        LogEvent.id.in_([alert.event_ids] if alert.event_ids else [])
    )
    event_count_result = await db.execute(event_count_stmt)
    event_count = event_count_result.scalar() or 0

    alert_dict = AlertResponse.model_validate(alert).model_dump()
    alert_dict["event_count"] = event_count

    return AlertResponse(**alert_dict)


@router.post(
    "/{alert_id}/feedback",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit alert feedback",
    description="Submit true positive or false positive verdict (Admin, Compliance Officer)",
)
async def submit_alert_feedback(
    alert_id: UUID,
    feedback_data: AlertFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> dict:
    """
    Submit feedback (TP/FP verdict) for an alert.

    Args:
        alert_id: Alert ID
        feedback_data: Verdict and comment
        db: Database session
        current_user: Current authenticated user (must be Admin or Compliance Officer)

    Returns:
        Status message

    Raises:
        HTTPException: 404 if alert not found, 422 if invalid verdict
    """
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalars().first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    user_id = current_user.get("user_id")

    try:
        rag_service = RAGService()
        await submit_feedback(
            db=db,
            alert_id=alert_id,
            verdict=feedback_data.verdict,
            comment=feedback_data.comment,
            user_id=user_id,
            rag_service=rag_service,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    alert.analyst_verdict = feedback_data.verdict
    alert.analyst_comment = feedback_data.comment
    alert.status = "resolved"
    alert.updated_at = datetime.now(timezone.utc)

    db.add(alert)
    await db.commit()

    return {
        "status": "feedback_recorded",
        "alert_id": alert_id,
        "verdict": feedback_data.verdict,
    }
