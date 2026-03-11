from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class LogEvent(Base):
    """
    Canonical log event after normalization.
    Agreed schema: timestamp, source, event_type, principal, action,
    resource, result, source_ip, asset_id, session_id, domain, raw_log.

    raw_log is stored as JSONB for efficient querying in PostgreSQL.
    """
    __tablename__ = "log_events"

    id            = Column(Integer, primary_key=True, index=True)

    # Core canonical schema fields
    timestamp     = Column(DateTime, nullable=False, index=True)
    source        = Column(String(100), nullable=False)             # vpn_server | firewall | app | cloud
    event_type    = Column(String(100), nullable=False, index=True) # authentication | network | api_request
    principal     = Column(String(255), nullable=True, index=True)  # user OR service actor (never "user")
    action        = Column(String(100), nullable=True)              # login_attempt | transfer | access
    resource      = Column(String(255), nullable=True)              # vpn_gateway | endpoint | bucket
    result        = Column(String(50),  nullable=True)              # success | failed | blocked
    source_ip     = Column(String(50),  nullable=True)              # always "source_ip" — never "ip_address"

    # Enrichment fields
    asset_id      = Column(String(100), nullable=True, index=True)  # e.g. "vpn-01" — human readable string
    session_id    = Column(String(100), nullable=True, index=True)  # correlate events from same session
    domain        = Column(String(100), nullable=True)              # department/BU for RBAC scoping

    # Raw log stored as JSONB — enables querying inside the raw log in PostgreSQL
    raw_log       = Column(JSONB, nullable=True)
    is_normalized  = Column(Boolean, default=True)
    is_quarantined = Column(Boolean, default=False)                 # malformed events (SRS FR-06)

    # AI scoring
    anomaly_score = Column(Float, nullable=True)                    # 0.0 – 1.0 from ML model

    ingested_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    alerts = relationship("Alert", back_populates="log_event")
