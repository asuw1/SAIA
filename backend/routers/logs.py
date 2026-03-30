"""Log ingestion and event query router for SAIA V4."""

import csv
import json
from io import StringIO, BytesIO
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Query,
    BackgroundTasks,
)
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..database import get_db
from ..middleware.auth import get_current_user, require_roles
from ..models.log_event import (
    LogEventResponse,
    LogUploadResponse,
    LogIngestRequest,
    UploadResponse,
)
from ..models.base import LogEvent, Upload
from ..services.ingestion import (
    parse_json_upload,
    parse_csv_upload,
    normalize_event,
    compute_quality_score,
)

router = APIRouter(prefix="/api/v1/logs", tags=["Logs"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/upload",
    response_model=LogUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload log file",
    description="Upload JSON or CSV log file (Admin, Compliance Officer only)",
)
async def upload_logs(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
    background_tasks: BackgroundTasks = None,
) -> LogUploadResponse:
    """
    Upload and ingest a log file.

    Args:
        file: JSON or CSV file upload
        db: Database session
        current_user: Current authenticated user
        background_tasks: FastAPI background tasks for async processing

    Returns:
        LogUploadResponse with ingestion stats

    Raises:
        HTTPException: 400 if file format invalid, 413 if too large
    """
    if file.size and file.size > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 100MB)",
        )

    upload_id = uuid4()
    filename = file.filename or "unknown"

    try:
        content = await file.read()

        if filename.endswith(".json"):
            events = parse_json_upload(content)
        elif filename.endswith(".csv"):
            events = parse_csv_upload(content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Use .json or .csv",
            )

    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format: {str(e)}",
        )

    events_parsed = len(events)
    events_accepted = 0
    events_quarantined = 0
    source_name = filename.split(".")[0]
    domain = "default"

    for event_dict in events:
        try:
            normalized = normalize_event(event_dict, source_name, domain)
            quality_score = compute_quality_score(normalized)

            log_event = LogEvent(
                id=uuid4(),
                upload_id=upload_id,
                timestamp=normalized.get("timestamp", datetime.now(timezone.utc)),
                source=normalized.get("source", source_name),
                event_type=normalized.get("event_type", "unknown"),
                principal=normalized.get("principal"),
                action=normalized.get("action"),
                resource=normalized.get("resource"),
                result=normalized.get("result"),
                source_ip=normalized.get("source_ip"),
                asset_id=normalized.get("asset_id"),
                domain=normalized.get("domain", domain),
                raw_log=normalized,
                quality_score=f"{quality_score:.3f}",
                is_quarantined=quality_score < 0.7,
            )

            db.add(log_event)

            if quality_score < 0.7:
                events_quarantined += 1
            else:
                events_accepted += 1

        except Exception as e:
            events_quarantined += 1
            continue

    upload_record = Upload(
        id=upload_id,
        user_id=current_user.get("user_id"),
        source_name=source_name,
        domain=domain,
        filename=filename,
        events_parsed=events_parsed,
        events_accepted=events_accepted,
        events_quarantined=events_quarantined,
        status="completed",
    )

    db.add(upload_record)
    await db.commit()

    return LogUploadResponse(
        upload_id=upload_id,
        events_parsed=events_parsed,
        events_accepted=events_accepted,
        events_quarantined=events_quarantined,
    )


@router.post(
    "/ingest",
    response_model=LogUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest JSON events",
    description="Ingest log events from JSON body (Admin, Compliance Officer only, rate limited 60/min)",
)
@limiter.limit("60/minute")
async def ingest_logs(
    request: LogIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
    background_tasks: BackgroundTasks = None,
) -> LogUploadResponse:
    """
    Ingest log events from JSON request body.

    Args:
        request: LogIngestRequest with events array
        db: Database session
        current_user: Current authenticated user
        background_tasks: FastAPI background tasks

    Returns:
        LogUploadResponse with ingestion stats

    Raises:
        HTTPException: 400 if events invalid
    """
    upload_id = uuid4()
    events = request.events or []

    if not events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No events provided",
        )

    events_parsed = len(events)
    events_accepted = 0
    events_quarantined = 0

    for event_dict in events:
        try:
            normalized = normalize_event(event_dict, request.source_name, request.domain)
            quality_score = compute_quality_score(normalized)

            log_event = LogEvent(
                id=uuid4(),
                upload_id=upload_id,
                timestamp=normalized.get("timestamp", datetime.now(timezone.utc)),
                source=normalized.get("source", request.source_name),
                event_type=normalized.get("event_type", "unknown"),
                principal=normalized.get("principal"),
                action=normalized.get("action"),
                resource=normalized.get("resource"),
                result=normalized.get("result"),
                source_ip=normalized.get("source_ip"),
                asset_id=normalized.get("asset_id"),
                domain=normalized.get("domain", request.domain),
                raw_log=normalized,
                quality_score=f"{quality_score:.3f}",
                is_quarantined=quality_score < 0.7,
            )

            db.add(log_event)

            if quality_score < 0.7:
                events_quarantined += 1
            else:
                events_accepted += 1

        except Exception as e:
            events_quarantined += 1
            continue

    upload_record = Upload(
        id=upload_id,
        user_id=current_user.get("user_id"),
        source_name=request.source_name,
        domain=request.domain,
        filename=f"{request.source_name}_ingest",
        events_parsed=events_parsed,
        events_accepted=events_accepted,
        events_quarantined=events_quarantined,
        status="completed",
    )

    db.add(upload_record)
    await db.commit()

    return LogUploadResponse(
        upload_id=upload_id,
        events_parsed=events_parsed,
        events_accepted=events_accepted,
        events_quarantined=events_quarantined,
    )


@router.get(
    "/events",
    response_model=list[LogEventResponse],
    status_code=status.HTTP_200_OK,
    summary="Query log events",
    description="Get paginated log events with filters",
)
async def query_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    domain: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    principal: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[LogEventResponse]:
    """
    Query log events with pagination and filters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        domain: Filter by domain
        event_type: Filter by event type
        principal: Filter by principal
        start_time: Filter by start timestamp
        end_time: Filter by end timestamp
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of LogEventResponse
    """
    user_data_scope = current_user.get("data_scope", ["*"])
    offset = (page - 1) * page_size

    filters = []

    if user_data_scope != ["*"]:
        filters.append(LogEvent.domain.in_(user_data_scope))

    if domain:
        filters.append(LogEvent.domain == domain)

    if event_type:
        filters.append(LogEvent.event_type == event_type)

    if principal:
        filters.append(LogEvent.principal == principal)

    if start_time:
        filters.append(LogEvent.timestamp >= start_time)

    if end_time:
        filters.append(LogEvent.timestamp <= end_time)

    stmt = select(LogEvent)
    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(LogEvent.timestamp)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    events = result.scalars().all()

    return [LogEventResponse.model_validate(e) for e in events]


@router.get(
    "/uploads",
    response_model=list[UploadResponse],
    status_code=status.HTTP_200_OK,
    summary="List upload batches",
    description="Get list of all upload batches with stats",
)
async def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[UploadResponse]:
    """
    List all log upload batches.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of UploadResponse
    """
    offset = (page - 1) * page_size

    stmt = select(Upload).order_by(desc(Upload.created_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    uploads = result.scalars().all()

    return [UploadResponse.model_validate(u) for u in uploads]
