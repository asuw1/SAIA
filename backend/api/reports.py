from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from schemas.report import ReportRequest, ReportOut
from services.report_service import generate_report, list_reports
from core.dependencies import get_current_user

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/", response_model=list[ReportOut])
def get_reports(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list_reports(db)


@router.post("/", response_model=ReportOut)
def create_report(
    data: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return generate_report(data, current_user.id, db)
