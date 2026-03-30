"""
AI / ML Anomaly Detection Service
Pair 1 (Firas + Abdulaziz) — responsible for this module.

Uses an Isolation Forest model to score log events.
Events with a score above the threshold trigger AI alerts.
The model is trained on historical normalized events.
"""

import numpy as np
from sqlalchemy.orm import Session
from models.log_event import LogEvent
from models.alert import Alert
from models.clause import Clause
from config import settings
from datetime import datetime, timezone, timedelta


# ── Feature extraction ────────────────────────────────────────────────────────

def extract_features(event: LogEvent) -> list[float]:
    """
    Convert a LogEvent into a numeric feature vector for the ML model.
    Expand this as the model matures.
    """
    hour = event.timestamp.hour if event.timestamp else 12
    is_failure = 1.0 if event.result in ("failure", "blocked", "denied") else 0.0
    is_after_hours = 1.0 if (hour < 7 or hour > 19) else 0.0
    source_map = {"auth": 0, "firewall": 1, "app": 2, "cloud": 3}
    source_val = float(source_map.get(event.source, -1))

    return [hour, is_failure, is_after_hours, source_val]


# ── Model ─────────────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Wrapper around scikit-learn's IsolationForest.
    Call train() with historical events, then score() on new ones.
    """

    def __init__(self):
        self.model = None
        self.is_trained = False

    def train(self, events: list[LogEvent]):
        from sklearn.ensemble import IsolationForest

        if len(events) < 10:
            return  # not enough data to train yet

        X = np.array([extract_features(e) for e in events])
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05,   # assume ~5% anomaly rate
            random_state=42,
        )
        self.model.fit(X)
        self.is_trained = True

    def score(self, event: LogEvent) -> float:
        """
        Returns anomaly score between 0.0 (normal) and 1.0 (anomalous).
        Returns 0.0 if model is not yet trained.
        """
        if not self.is_trained or self.model is None:
            return 0.0

        features = np.array([extract_features(event)]).reshape(1, -1)
        # IsolationForest returns -1 (anomaly) or 1 (normal)
        raw_score = self.model.decision_function(features)[0]
        # Convert to 0–1 range (higher = more anomalous)
        normalized = float(1.0 - (raw_score + 0.5))
        return max(0.0, min(1.0, normalized))


# Singleton — shared across requests
detector = AnomalyDetector()


# ── Alert creation ────────────────────────────────────────────────────────────

def create_ai_alert(event: LogEvent, score: float, db: Session) -> Alert:
    """Create an AI-triggered alert. Maps to a generic anomaly clause."""
    # Use a fallback clause — in production, map to the best matching clause
    fallback_clause = db.query(Clause).first()
    clause_id = fallback_clause.id if fallback_clause else 1

    severity = "Critical" if score > 0.85 else "High" if score > 0.70 else "Medium"
    sla_hours = {"Critical": 2, "High": 8, "Medium": 24}

    alert = Alert(
        title       = f"AI Anomaly Detected — score {score:.2f}",
        description = f"Isolation Forest flagged this event with anomaly score {score:.2f}",
        severity    = severity,
        status      = "open",
        source      = "ai",
        clause_id   = clause_id,
        log_event_id= event.id,
        detected_at = datetime.now(timezone.utc),
        sla_deadline= datetime.now(timezone.utc) + timedelta(hours=sla_hours[severity]),
    )
    db.add(alert)
    return alert


# ── Main entry point ──────────────────────────────────────────────────────────

def run_ai_analysis(events: list[LogEvent], db: Session) -> list[Alert]:
    """
    Score each event and create alerts for those above the threshold.
    Also persists the anomaly_score back to the LogEvent row.
    """
    if settings.AI_MODE == "rules_only":
        return []

    ai_alerts = []

    for event in events:
        score = detector.score(event)
        event.anomaly_score = score   # store score on the event

        if score >= settings.ANOMALY_THRESHOLD:
            alert = create_ai_alert(event, score, db)
            ai_alerts.append(alert)

    if ai_alerts:
        db.commit()

    return ai_alerts
