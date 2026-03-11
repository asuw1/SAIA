from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Report(Base):
    """
    A generated compliance report.
    Stores metadata; actual file content lives on disk or object storage.
    """
    __tablename__ = "reports"

    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String(255), nullable=False)
    framework        = Column(String(20), nullable=True)           # NCA | SAMA | CST | IA | ALL
    date_from        = Column(DateTime, nullable=False)
    date_to          = Column(DateTime, nullable=False)
    export_format    = Column(String(10), default="pdf")           # pdf | csv | json
    file_path        = Column(String(500), nullable=True)
    events_count     = Column(Integer, default=0)
    violations_count = Column(Integer, default=0)
    generated_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    generated_by_user = relationship("User")


class AuditLog(Base):
    """
    Immutable system-level audit trail — every action by every user is recorded.
    detail stored as JSONB so you can query specific change fields in PostgreSQL.
    This table must never be updated or deleted (SRS FR-38, NFR-06).
    """
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    action      = Column(String(100), nullable=False)              # create_rule | resolve_alert | login
    resource    = Column(String(100), nullable=True)               # rule | alert | case | report
    resource_id = Column(Integer, nullable=True)
    detail      = Column(JSONB, nullable=True)                     # change details as JSONB
    ip_address  = Column(String(50), nullable=True)
    timestamp   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")
