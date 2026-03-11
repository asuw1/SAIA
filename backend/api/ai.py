from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.log_event import LogEvent
from services.ai_service import detector
from core.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/ai", tags=["AI Analytics"])


@router.get("/status")
def model_status(_: User = Depends(get_current_user)):
    """Check if the anomaly detection model is trained."""
    return {
        "is_trained": detector.is_trained,
        "model_type": "IsolationForest",
        "threshold": 0.65,
    }


@router.post("/train")
def train_model(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("Admin")),
):
    """
    Trigger model training on all stored log events.
    Should be called after initial data ingestion.
    """
    events = db.query(LogEvent).filter(LogEvent.is_quarantined == False).all()
    detector.train(events)
    return {
        "message": f"Model trained on {len(events)} events.",
        "is_trained": detector.is_trained,
    }
