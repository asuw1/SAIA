"""
Rule Engine Service
Pair 1 (Firas + Abdulaziz) — responsible for this module.

Evaluates active rules against normalized LogEvents.
Each rule has a logic_json field that defines its conditions.
When a rule fires, an Alert is created with the matching clause reference.
"""

import json
from sqlalchemy.orm import Session
from models.rule import Rule
from models.alert import Alert
from models.log_event import LogEvent
from datetime import datetime, timezone, timedelta


def load_active_rules(db: Session) -> list[Rule]:
    """Load all active rules from the database."""
    return db.query(Rule).filter(Rule.status == "active").all()


def evaluate_rule(rule: Rule, event: LogEvent) -> bool:
    """
    Evaluate a single rule against a log event.
    Supported conditions in logic_json:
      - event_type: exact match
      - result: exact match (e.g. "failure")
      - action: exact match
      - threshold: used with count-based rules (future)
      - time_window: outside_business_hours (basic check)
    """
    try:
        conditions = rule.logic_json if isinstance(rule.logic_json, dict) else json.loads(rule.logic_json)
    except (json.JSONDecodeError, TypeError):
        return False

    # Each condition must pass for the rule to fire (AND logic)
    for field, expected in conditions.items():
        if field == "event_type" and event.event_type != expected:
            return False
        elif field == "result" and event.result != expected:
            return False
        elif field == "action" and event.action != expected:
            return False
        elif field == "source" and event.source != expected:
            return False
        elif field == "outside_business_hours":
            hour = event.timestamp.hour
            if not (hour < 7 or hour > 19):   # business hours = 07:00–19:00
                return False

    return True


def create_alert_from_rule(rule: Rule, event: LogEvent, db: Session) -> Alert:
    """Create and persist an Alert when a rule fires."""
    sla_hours = {"Critical": 2, "High": 8, "Medium": 24, "Low": 72}
    hours = sla_hours.get(rule.severity, 24)

    alert = Alert(
        title       = f"{rule.name} — {rule.severity} violation",
        description = rule.description,
        severity    = rule.severity,
        status      = "open",
        source      = "rule",
        rule_id     = rule.id,
        clause_id   = rule.clause_id,
        log_event_id= event.id,
        detected_at = datetime.now(timezone.utc),
        sla_deadline= datetime.now(timezone.utc) + timedelta(hours=hours),
    )
    db.add(alert)
    return alert


def run_rule_engine(events: list[LogEvent], db: Session) -> list[Alert]:
    """
    Main entry point.
    Runs all active rules against a batch of log events.
    Returns all newly created alerts.
    """
    rules = load_active_rules(db)
    triggered_alerts = []

    for event in events:
        for rule in rules:
            if evaluate_rule(rule, event):
                alert = create_alert_from_rule(rule, event, db)
                triggered_alerts.append(alert)

    if triggered_alerts:
        db.commit()

    return triggered_alerts
