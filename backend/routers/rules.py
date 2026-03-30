"""Rule management router for SAIA V4."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user, require_roles
from ..models.rule import (
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleTestResult,
)
from ..models.base import Rule, LogEvent
from ..services.rule_engine import RuleEngine

router = APIRouter(prefix="/api/v1/rules", tags=["Rules"])


@router.get(
    "",
    response_model=list[RuleResponse],
    status_code=status.HTTP_200_OK,
    summary="List rules",
    description="Get all rules",
)
async def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    domain: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[RuleResponse]:
    """
    List all rules with optional filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        domain: Filter by domain
        is_active: Filter by active status
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of RuleResponse
    """
    offset = (page - 1) * page_size
    filters = []

    if domain:
        filters.append(Rule.domain == domain)

    if is_active is not None:
        filters.append(Rule.is_active == is_active)

    stmt = select(Rule)
    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(desc(Rule.created_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    rules = result.scalars().all()

    return [RuleResponse.model_validate(r) for r in rules]


@router.post(
    "",
    response_model=RuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create rule",
    description="Create new rule (Admin, Compliance Officer only)",
)
async def create_rule(
    rule_data: RuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> RuleResponse:
    """
    Create a new rule.

    Args:
        rule_data: Rule creation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        RuleResponse with created rule

    Raises:
        HTTPException: 409 if rule with same name already exists
    """
    stmt = select(Rule).where(
        and_(
            Rule.name == rule_data.name,
            Rule.domain == rule_data.domain,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rule with this name already exists in domain",
        )

    new_rule = Rule(
        id=uuid4(),
        name=rule_data.name,
        description=rule_data.description,
        domain=rule_data.domain,
        clause_reference=rule_data.clause_reference,
        severity=rule_data.severity,
        conditions=rule_data.conditions.model_dump(),
        is_active=False,
        version="1.0",
        author_id=current_user.get("user_id"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)

    return RuleResponse.model_validate(new_rule)


@router.patch(
    "/{rule_id}",
    response_model=RuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update rule",
    description="Update rule definition (Admin, Compliance Officer only)",
)
async def update_rule(
    rule_id: UUID,
    rule_data: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> RuleResponse:
    """
    Update a rule.

    Args:
        rule_id: Rule ID
        rule_data: Fields to update
        db: Database session
        current_user: Current authenticated user

    Returns:
        RuleResponse with updated rule

    Raises:
        HTTPException: 404 if rule not found
    """
    stmt = select(Rule).where(Rule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalars().first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    update_dict = rule_data.model_dump(exclude_unset=True)

    if "name" in update_dict:
        rule.name = update_dict["name"]

    if "description" in update_dict:
        rule.description = update_dict["description"]

    if "severity" in update_dict:
        rule.severity = update_dict["severity"]

    if "conditions" in update_dict:
        rule.conditions = update_dict["conditions"].model_dump()

    if "is_active" in update_dict:
        rule.is_active = update_dict["is_active"]

    rule.updated_at = datetime.now(timezone.utc)

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return RuleResponse.model_validate(rule)


@router.post(
    "/{rule_id}/publish",
    status_code=status.HTTP_200_OK,
    summary="Publish/activate rule",
    description="Publish and activate a rule (Admin only)",
)
async def publish_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin")),
) -> dict:
    """
    Publish and activate a rule for production use.

    Args:
        rule_id: Rule ID
        db: Database session
        current_user: Current authenticated user (must be Admin)

    Returns:
        Status message

    Raises:
        HTTPException: 404 if rule not found
    """
    stmt = select(Rule).where(Rule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalars().first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    rule.is_active = True
    rule.updated_at = datetime.now(timezone.utc)

    db.add(rule)
    await db.commit()

    return {
        "status": "published",
        "rule_id": rule_id,
        "message": "Rule activated and ready for evaluation",
    }


@router.post(
    "/{rule_id}/test",
    response_model=RuleTestResult,
    status_code=status.HTTP_200_OK,
    summary="Test rule",
    description="Test rule against recent log events",
)
async def test_rule(
    rule_id: UUID,
    lookback_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin", "Compliance Officer")),
) -> RuleTestResult:
    """
    Test a rule against recent log events.

    Args:
        rule_id: Rule ID
        lookback_hours: Hours back to search for matching events
        db: Database session
        current_user: Current authenticated user

    Returns:
        RuleTestResult with matched events

    Raises:
        HTTPException: 404 if rule not found
    """
    stmt = select(Rule).where(Rule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalars().first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    events_stmt = select(LogEvent).where(
        and_(
            LogEvent.domain == rule.domain,
            LogEvent.timestamp >= since,
        )
    ).limit(10000)

    events_result = await db.execute(events_stmt)
    events = events_result.scalars().all()

    rule_engine = RuleEngine()
    matched_count = 0
    sample_matches = []

    for event in events:
        try:
            conditions = rule.conditions
            field_checks = conditions.get("field_checks", [])

            all_match = True
            for check in field_checks:
                field = check.get("field")
                operator = check.get("operator")
                value = check.get("value")

                event_value = event.raw_log.get(field)

                if operator == "equals" and event_value != value:
                    all_match = False
                    break
                elif operator == "contains" and value not in str(event_value):
                    all_match = False
                    break

            if all_match:
                matched_count += 1
                if len(sample_matches) < 5:
                    sample_matches.append(event.raw_log)

        except Exception as e:
            continue

    return RuleTestResult(
        matched_events=matched_count,
        sample_matches=sample_matches,
    )
