from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Case(Base):
    """
    A case groups related alerts together for investigation.
    Status lifecycle: open → in_progress → resolved → verified  (SRS FR-21)
    """
    __tablename__ = "cases"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String(255), nullable=False)
    description  = Column(Text, nullable=True)
    status       = Column(String(30), default="open")              # open | in_progress | resolved | verified
    assigned_to  = Column(Integer, ForeignKey("users.id"), nullable=True)
    sla_deadline = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at  = Column(DateTime, nullable=True)

    alerts = relationship("Alert", back_populates="case")


class AlertComment(Base):
    """
    Analyst comments/notes on a specific alert (SRS FR-23).
    """
    __tablename__ = "alert_comments"

    id         = Column(Integer, primary_key=True, index=True)
    alert_id   = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    alert = relationship("Alert", back_populates="comments")
    user  = relationship("User")
