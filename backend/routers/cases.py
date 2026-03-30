"""Case management router for SAIA V4."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    BackgroundTasks,
)
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user, require_roles
from ..models.case import (
    CaseCreate,
    CaseUpdate,
    CaseResponse,
    EvidenceGenerateResponse,
    NarrativeResponse,
)
from ..models.base import Case, Alert
from ..services.narrative_service import generate_narrative
from ..services.llm_client import LLMClient
from ..services.rag_service import RAGService

router = APIRouter(prefix="/api/v1/cases", tags=["Cases"])


@router.get(
    "",
    response_model=list[CaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List cases",
    description="Get paginated list of cases",
)
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status_filter: Optional[str] = Query(None, alias="status"),
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[CaseResponse]:
    """
    List cases with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        status_filter: Filter by status (open, in_progress, resolved, verified)
        domain: Filter by domain
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of CaseResponse
    """
    user_data_scope = current_user.get("data_scope", ["*"])
    offset = (page - 1) * page_size

    filters = []

    if user_data_scope != ["*"]:
        filters.append(Case.domain.in_(user_data_scope))

    if status_filter:
        filters.append(Case.status == status_filter)

    if domain:
        filters.append(Case.domain == domain)

    stmt = select(Case)
    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(Case.created_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    cases = result.scalars().all()

    case_responses = []
    for case in cases:
        alert_count_stmt = select(func.count(Alert.id)).where(Alert.case_id == case.id)
        alert_count_result = await db.execute(alert_count_stmt)
        alert_count = alert_count_result.scalar() or 0

        case_dict = CaseResponse.model_validate(case).model_dump()
        case_dict["alert_count"] = alert_count
        case_responses.append(CaseResponse(**case_dict))

    return case_responses


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create case",
    description="Create case from alert group",
)
async def create_case(
    case_data: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CaseResponse:
    """
    Create a new case from related alerts.

    Args:
        case_data: Case creation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        CaseResponse with created case

    Raises:
        HTTPException: 400 if no alerts provided or not found
    """
    if not case_data.alert_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one alert ID required",
        )

    stmt = select(func.count(Alert.id)).where(Alert.id.in_(case_data.alert_ids))
    result = await db.execute(stmt)
    found_count = result.scalar() or 0

    if found_count != len(case_data.alert_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more alert IDs not found",
        )

    stmt = select(Alert).where(Alert.id.in_(case_data.alert_ids))
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    domain = alerts[0].domain if alerts else "default"

    new_case = Case(
        id=uuid4(),
        case_number=None,
        title=case_data.title,
        description=case_data.description,
        status="open",
        severity=case_data.severity,
        domain=domain,
        assigned_to=None,
        narrative_draft=None,
        narrative_approved=False,
        narrative_approved_by=None,
        narrative_approved_at=None,
        narrative_status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        resolved_at=None,
    )

    db.add(new_case)
    await db.flush()

    for alert in alerts:
        alert.case_id = new_case.id
        db.add(alert)

    await db.commit()
    await db.refresh(new_case)

    return CaseResponse(
        **CaseResponse.model_validate(new_case).model_dump(),
        alert_count=len(case_data.alert_ids),
    )


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update case",
    description="Update case status and details",
)
async def update_case(
    case_id: UUID,
    case_data: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CaseResponse:
    """
    Update a case.

    Args:
        case_id: Case ID
        case_data: Fields to update
        db: Database session
        current_user: Current authenticated user

    Returns:
        CaseResponse with updated case

    Raises:
        HTTPException: 404 if case not found
    """
    stmt = select(Case).where(Case.id == case_id)
    result = await db.execute(stmt)
    case = result.scalars().first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    update_dict = case_data.model_dump(exclude_unset=True)

    if "status" in update_dict:
        case.status = update_dict["status"]
        if update_dict["status"] == "resolved":
            case.resolved_at = datetime.now(timezone.utc)

    if "assigned_to" in update_dict:
        case.assigned_to = update_dict["assigned_to"]

    if "title" in update_dict:
        case.title = update_dict["title"]

    if "description" in update_dict:
        case.description = update_dict["description"]

    case.updated_at = datetime.now(timezone.utc)

    db.add(case)
    await db.commit()
    await db.refresh(case)

    alert_count_stmt = select(func.count(Alert.id)).where(Alert.case_id == case.id)
    alert_count_result = await db.execute(alert_count_stmt)
    alert_count = alert_count_result.scalar() or 0

    case_dict = CaseResponse.model_validate(case).model_dump()
    case_dict["alert_count"] = alert_count

    return CaseResponse(**case_dict)


@router.post(
    "/{case_id}/generate-evidence",
    response_model=EvidenceGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate evidence narrative",
    description="Async background task to generate case narrative",
)
async def generate_evidence(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> EvidenceGenerateResponse:
    """
    Trigger background task to generate evidence narrative.

    Args:
        case_id: Case ID
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        EvidenceGenerateResponse with 202 status

    Raises:
        HTTPException: 404 if case not found
    """
    stmt = select(Case).where(Case.id == case_id)
    result = await db.execute(stmt)
    case = result.scalars().first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    case.narrative_status = "generating"
    db.add(case)
    await db.commit()

    llm_client = LLMClient()
    rag_service = RAGService()

    background_tasks.add_task(
        generate_narrative,
        db=db,
        case_id=case_id,
        user_role=current_user.get("role"),
        data_scope=current_user.get("data_scope", ["*"]),
        llm_client=llm_client,
        rag_service=rag_service,
    )

    return EvidenceGenerateResponse(
        case_id=case_id,
        status="pending",
        message="Narrative generation queued for processing",
    )


@router.get(
    "/{case_id}/narrative",
    response_model=NarrativeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get case narrative",
    description="Retrieve case narrative content",
)
async def get_narrative(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> NarrativeResponse:
    """
    Get the narrative content for a case.

    Args:
        case_id: Case ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        NarrativeResponse with narrative content

    Raises:
        HTTPException: 404 if case not found
    """
    stmt = select(Case).where(Case.id == case_id)
    result = await db.execute(stmt)
    case = result.scalars().first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    return NarrativeResponse(
        narrative_draft=case.narrative_draft,
        narrative_status=case.narrative_status,
        narrative_approved=case.narrative_approved,
    )


@router.patch(
    "/{case_id}/approve-narrative",
    response_model=NarrativeResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve narrative draft",
    description="Approve and finalize case narrative",
)
async def approve_narrative(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> NarrativeResponse:
    """
    Approve a case narrative draft.

    Args:
        case_id: Case ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        NarrativeResponse with updated status

    Raises:
        HTTPException: 404 if case not found, 400 if no narrative to approve
    """
    stmt = select(Case).where(Case.id == case_id)
    result = await db.execute(stmt)
    case = result.scalars().first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    if not case.narrative_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No narrative draft to approve",
        )

    case.narrative_approved = True
    case.narrative_approved_by = current_user.get("user_id")
    case.narrative_approved_at = datetime.now(timezone.utc)
    case.narrative_status = "approved"

    db.add(case)
    await db.commit()
    await db.refresh(case)

    return NarrativeResponse(
        narrative_draft=case.narrative_draft,
        narrative_status=case.narrative_status,
        narrative_approved=case.narrative_approved,
    )
