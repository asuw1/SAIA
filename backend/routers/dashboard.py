"""Dashboard analytics router for SAIA V4."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user
from ..models.dashboard import (
    KPIResponse,
    AnomalyDistributionResponse,
    AnomalyBucket,
    PrecisionTrackerResponse,
    PrecisionDataPoint,
    ModelHealthResponse,
    DriftAlert,
    FeedbackSummary,
)
from ..models.base import Alert, Case, LogEvent

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get(
    "/kpis",
    response_model=KPIResponse,
    status_code=200,
    summary="Dashboard KPIs",
    description="Get key performance indicator summary",
)
async def get_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> KPIResponse:
    """
    Get dashboard KPI metrics.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        KPIResponse with KPI values
    """
    user_data_scope = current_user.get("data_scope", ["*"])

    filters = []
    if user_data_scope != ["*"]:
        filters.append(Alert.domain.in_(user_data_scope))

    active_alerts_stmt = select(func.count(Alert.id)).where(
        and_(Alert.status.in_(["open", "investigating"]), *filters)
    )
    active_alerts_result = await db.execute(active_alerts_stmt)
    active_alerts = active_alerts_result.scalar() or 0

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    resolved_cases_stmt = select(func.count(Case.id)).where(
        and_(Case.status == "resolved", Case.resolved_at >= thirty_days_ago, *filters)
    )
    resolved_cases_result = await db.execute(resolved_cases_stmt)
    resolved_cases_30d = resolved_cases_result.scalar() or 0

    pending_reports_stmt = select(func.count(Case.id)).where(
        and_(Case.narrative_status.in_(["draft", "generating"]), *filters)
    )
    pending_reports_result = await db.execute(pending_reports_stmt)
    pending_reports = pending_reports_result.scalar() or 0

    avg_response_time_stmt = select(
        func.avg(func.extract("epoch", Alert.updated_at - Alert.created_at)) / 3600
    ).where(and_(Alert.status == "resolved", *filters))
    avg_response_time_result = await db.execute(avg_response_time_stmt)
    avg_response_time_hours = float(avg_response_time_result.scalar() or 0)

    quality_score_stmt = select(func.avg(LogEvent.quality_score)).where(
        and_(LogEvent.is_quarantined == False, *filters)
    )
    quality_score_result = await db.execute(quality_score_stmt)
    data_quality_score = float(quality_score_result.scalar() or 0.7)

    return KPIResponse(
        active_alerts=active_alerts,
        resolved_cases_30d=resolved_cases_30d,
        pending_reports=pending_reports,
        avg_response_time_hours=avg_response_time_hours,
        data_quality_score=data_quality_score,
    )


@router.get(
    "/anomaly-distribution",
    response_model=AnomalyDistributionResponse,
    status_code=200,
    summary="Anomaly score distribution",
    description="Get histogram of anomaly scores with threshold",
)
async def get_anomaly_distribution(
    window_hours: int = Query(24, ge=1, le=720),
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AnomalyDistributionResponse:
    """
    Get anomaly score distribution histogram.

    Args:
        window_hours: Hours back to analyze
        domain: Optional domain filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        AnomalyDistributionResponse with bucketed data
    """
    user_data_scope = current_user.get("data_scope", ["*"])
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    filters = [LogEvent.timestamp >= since]
    if user_data_scope != ["*"]:
        filters.append(LogEvent.domain.in_(user_data_scope))
    if domain:
        filters.append(LogEvent.domain == domain)

    events_stmt = select(LogEvent).where(and_(*filters))
    events_result = await db.execute(events_stmt)
    events = events_result.scalars().all()

    buckets_dict = {
        "0.0-0.1": 0,
        "0.1-0.2": 0,
        "0.2-0.3": 0,
        "0.3-0.4": 0,
        "0.4-0.5": 0,
        "0.5-0.6": 0,
        "0.6-0.7": 0,
        "0.7-0.8": 0,
        "0.8-0.9": 0,
        "0.9-1.0": 0,
    }

    flagged_count = 0

    for event in events:
        if event.anomaly_score is not None:
            score = event.anomaly_score
            if score < 0.1:
                buckets_dict["0.0-0.1"] += 1
            elif score < 0.2:
                buckets_dict["0.1-0.2"] += 1
            elif score < 0.3:
                buckets_dict["0.2-0.3"] += 1
            elif score < 0.4:
                buckets_dict["0.3-0.4"] += 1
            elif score < 0.5:
                buckets_dict["0.4-0.5"] += 1
            elif score < 0.6:
                buckets_dict["0.5-0.6"] += 1
            elif score < 0.7:
                buckets_dict["0.6-0.7"] += 1
            elif score < 0.8:
                buckets_dict["0.7-0.8"] += 1
            elif score < 0.9:
                buckets_dict["0.8-0.9"] += 1
            else:
                buckets_dict["0.9-1.0"] += 1

            if event.is_flagged:
                flagged_count += 1

    buckets = [
        AnomalyBucket(range_start=0.0, range_end=0.1, count=buckets_dict["0.0-0.1"]),
        AnomalyBucket(range_start=0.1, range_end=0.2, count=buckets_dict["0.1-0.2"]),
        AnomalyBucket(range_start=0.2, range_end=0.3, count=buckets_dict["0.2-0.3"]),
        AnomalyBucket(range_start=0.3, range_end=0.4, count=buckets_dict["0.3-0.4"]),
        AnomalyBucket(range_start=0.4, range_end=0.5, count=buckets_dict["0.4-0.5"]),
        AnomalyBucket(range_start=0.5, range_end=0.6, count=buckets_dict["0.5-0.6"]),
        AnomalyBucket(range_start=0.6, range_end=0.7, count=buckets_dict["0.6-0.7"]),
        AnomalyBucket(range_start=0.7, range_end=0.8, count=buckets_dict["0.7-0.8"]),
        AnomalyBucket(range_start=0.8, range_end=0.9, count=buckets_dict["0.8-0.9"]),
        AnomalyBucket(range_start=0.9, range_end=1.0, count=buckets_dict["0.9-1.0"]),
    ]

    return AnomalyDistributionResponse(
        buckets=buckets,
        threshold=0.7,
        total_events=len(events),
        flagged_events=flagged_count,
    )


@router.get(
    "/precision-tracker",
    response_model=PrecisionTrackerResponse,
    status_code=200,
    summary="Precision tracking",
    description="Get rolling precision/recall metrics",
)
async def get_precision_tracker(
    window_days: int = Query(30, ge=1, le=365),
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> PrecisionTrackerResponse:
    """
    Get rolling precision metrics from analyst feedback.

    Args:
        window_days: Days back to analyze
        domain: Optional domain filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        PrecisionTrackerResponse with daily precision data
    """
    user_data_scope = current_user.get("data_scope", ["*"])
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    filters = [Alert.analyst_verdict.isnot(None), Alert.updated_at >= since]
    if user_data_scope != ["*"]:
        filters.append(Alert.domain.in_(user_data_scope))
    if domain:
        filters.append(Alert.domain == domain)

    alerts_stmt = select(Alert).where(and_(*filters))
    alerts_result = await db.execute(alerts_stmt)
    alerts = alerts_result.scalars().all()

    daily_data = {}
    for alert in alerts:
        if alert.updated_at:
            date_key = alert.updated_at.date().isoformat()
            if date_key not in daily_data:
                daily_data[date_key] = {"tp": 0, "fp": 0, "domain": domain or alert.domain}

            if alert.analyst_verdict == "true_positive":
                daily_data[date_key]["tp"] += 1
            elif alert.analyst_verdict == "false_positive":
                daily_data[date_key]["fp"] += 1

    data_points = []
    total_tp = 0
    total_fp = 0

    for date_key in sorted(daily_data.keys()):
        data = daily_data[date_key]
        tp = data["tp"]
        fp = data["fp"]
        total = tp + fp

        total_tp += tp
        total_fp += fp

        precision = tp / total if total > 0 else 0.0

        data_points.append(
            PrecisionDataPoint(
                date=date_key,
                precision=precision,
                tp_count=tp,
                fp_count=fp,
                domain=data["domain"],
            )
        )

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0

    return PrecisionTrackerResponse(
        data_points=data_points,
        overall_precision=overall_precision,
        target_precision=0.95,
        total_tp=total_tp,
        total_fp=total_fp,
    )


@router.get(
    "/model-health",
    response_model=ModelHealthResponse,
    status_code=200,
    summary="Model health metrics",
    description="Get system health and model performance metrics",
)
async def get_model_health(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ModelHealthResponse:
    """
    Get model and system health metrics.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        ModelHealthResponse with health data
    """
    user_data_scope = current_user.get("data_scope", ["*"])

    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    filters = [LogEvent.timestamp >= last_24h]
    if user_data_scope != ["*"]:
        filters.append(LogEvent.domain.in_(user_data_scope))

    processed_stmt = select(func.count(LogEvent.id)).where(and_(*filters))
    processed_result = await db.execute(processed_stmt)
    events_processed_24h = processed_result.scalar() or 0

    flagged_stmt = select(func.count(LogEvent.id)).where(
        and_(LogEvent.is_flagged == True, *filters)
    )
    flagged_result = await db.execute(flagged_stmt)
    events_flagged_24h = flagged_result.scalar() or 0

    quarantined_stmt = select(func.count(LogEvent.id)).where(
        and_(LogEvent.is_quarantined == True, *filters)
    )
    quarantined_result = await db.execute(quarantined_stmt)
    events_quarantined_24h = quarantined_result.scalar() or 0

    feedback_filters = [Alert.analyst_verdict.isnot(None)]
    if user_data_scope != ["*"]:
        feedback_filters.append(Alert.domain.in_(user_data_scope))

    tp_stmt = select(func.count(Alert.id)).where(
        and_(Alert.analyst_verdict == "true_positive", *feedback_filters)
    )
    tp_result = await db.execute(tp_stmt)
    tp_count = tp_result.scalar() or 0

    fp_stmt = select(func.count(Alert.id)).where(
        and_(Alert.analyst_verdict == "false_positive", *feedback_filters)
    )
    fp_result = await db.execute(fp_stmt)
    fp_count = fp_result.scalar() or 0

    feedback_precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0

    return ModelHealthResponse(
        events_processed_24h=events_processed_24h,
        events_flagged_24h=events_flagged_24h,
        events_quarantined_24h=events_quarantined_24h,
        llm_queue_depth=0,
        llm_avg_latency_ms=150.0,
        active_baselines=5,
        drift_alerts=[],
        feedback_this_month=FeedbackSummary(
            tp=tp_count,
            fp=fp_count,
            precision=feedback_precision,
        ),
    )
