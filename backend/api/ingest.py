from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from schemas.log_event import IngestResponse
from services.ingestion_service import ingest_logs, parse_json_logs, parse_csv_logs
from services.rule_engine import run_rule_engine
from services.ai_service import run_ai_analysis
from core.dependencies import get_current_user

router = APIRouter(prefix="/api/ingest", tags=["Log Ingestion"])


@router.post("/upload", response_model=IngestResponse)
async def upload_logs(
    file: UploadFile = File(...),
    source: str = Form(...),                   # auth | firewall | app | cloud
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a JSON or CSV log file for ingestion.
    After normalization, the rule engine and AI service both run automatically.
    """
    if source not in ("auth", "firewall", "app", "cloud"):
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    content = await file.read()
    filename = file.filename or ""

    if filename.endswith(".json"):
        raw_entries = parse_json_logs(content)
    elif filename.endswith(".csv"):
        raw_entries = parse_csv_logs(content)
    else:
        raise HTTPException(status_code=400, detail="Only .json and .csv files are supported")

    # Normalize and persist
    result = ingest_logs(raw_entries, source, db)
    saved_events = result["saved_events"]

    # Run detection pipeline
    rule_alerts = run_rule_engine(saved_events, db)
    ai_alerts   = run_ai_analysis(saved_events, db)
    total_alerts = len(rule_alerts) + len(ai_alerts)

    return IngestResponse(
        total_received   = result["total_received"],
        normalized       = result["normalized"],
        quarantined      = result["quarantined"],
        alerts_triggered = total_alerts,
        message          = f"Ingestion complete. {total_alerts} alert(s) triggered.",
    )
