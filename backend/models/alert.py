from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Alert(Base):
    """
    An alert is generated when a rule fires OR the AI detects an anomaly.
    Always references the triggering clause for regulatory traceability.
    Status lifecycle: open → investigating → resolved → verified
    """
    __tablename__ = "alerts"

    id            = Column(Integer, primary_key=True, index=True)
    title         = Column(String(255), nullable=False)
    description   = Column(Text, nullable=True)
    severity      = Column(String(20), nullable=False, index=True) # Critical | High | Medium | Low
    status        = Column(String(30), default="open", index=True) # open | investigating | resolved | verified
    source        = Column(String(20), default="rule")             # rule | ai | both

    # Foreign keys
    rule_id       = Column(Integer, ForeignKey("rules.id"), nullable=True)      # null if AI-only alert
    clause_id     = Column(Integer, ForeignKey("clauses.id"), nullable=False)
    log_event_id  = Column(Integer, ForeignKey("log_events.id"), nullable=True)
    assigned_to   = Column(Integer, ForeignKey("users.id"), nullable=True)
    case_id       = Column(Integer, ForeignKey("cases.id"), nullable=True)

    # SLA tracking (SRS FR-24)
    detected_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sla_deadline  = Column(DateTime, nullable=True)
    resolved_at   = Column(DateTime, nullable=True)
    is_overdue    = Column(Boolean, default=False)

    rule          = relationship("Rule", back_populates="alerts")
    clause        = relationship("Clause", back_populates="alerts")
    log_event     = relationship("LogEvent", back_populates="alerts")
    assigned_user = relationship("User", back_populates="alerts")
    case          = relationship("Case", back_populates="alerts")
    comments      = relationship("AlertComment", back_populates="alert")
