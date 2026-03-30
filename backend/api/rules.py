from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.rule import Rule
from schemas.rule import RuleCreate, RuleUpdate, RuleOut
from core.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/rules", tags=["Rules Management"])


@router.get("/", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Rule).order_by(Rule.created_at.desc()).all()


@router.post("/", response_model=RuleOut)
def create_rule(
    data: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin", "Auditor")),
):
    rule = Rule(**data.model_dump(), author_id=current_user.id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    data: RuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("Admin", "Auditor")),
):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/{rule_id}/publish", response_model=RuleOut)
def publish_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("Admin")),
):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.status = "active"
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def archive_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("Admin")),
):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.status = "archived"
    db.commit()
