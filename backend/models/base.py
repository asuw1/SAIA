"""SQLAlchemy ORM models for SAIA V4."""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
from uuid import uuid4

Base = declarative_base()


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String(50), nullable=False)
    data_scope = Column(ARRAY(String), default=["*"], nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class LogEvent(Base):
    """Log event model for ingested security logs."""

    __tablename__ = "log_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id"), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    principal = Column(String(255), nullable=True, index=True)
    action = Column(String(255), nullable=True)
    resource = Column(String(255), nullable=True)
    result = Column(String(50), nullable=True)
    source_ip = Column(String(50), nullable=True)
    asset_id = Column(String(255), nullable=True)
    domain = Column(String(100), nullable=False, index=True)
    raw_log = Column(JSONB, nullable=False)
    quality_score = Column(String(10), nullable=True)
    is_quarantined = Column(Boolean, default=False, index=True)
    anomaly_score = Column(String(10), nullable=True, index=True)
    is_flagged = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class Upload(Base):
    """Log upload batch metadata."""

    __tablename__ = "uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    source_name = Column(String(255), nullable=False)
    domain = Column(String(100), nullable=False)
    filename = Column(String(255), nullable=False)
    events_parsed = Column(Integer, default=0)
    events_accepted = Column(Integer, default=0)
    events_quarantined = Column(Integer, default=0)
    status = Column(String(50), default="in_progress")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Rule(Base):
    """Detection rule definition."""

    __tablename__ = "rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String(100), nullable=False, index=True)
    clause_reference = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    conditions = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=False, index=True)
    version = Column(String(20), default="1.0")
    author_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Alert(Base):
    """Security alert raised by rule or AI model."""

    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_number = Column(Integer, autoincrement=True)
    domain = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False)
    status = Column(String(50), default="open", index=True)
    source = Column(String(50), nullable=False)
    entity_principal = Column(String(255), nullable=True, index=True)
    clause_reference = Column(String(100), nullable=False)
    anomaly_score = Column(String(10), nullable=True)
    top_features = Column(JSONB, nullable=True)
    triggered_rules = Column(JSONB, nullable=True)
    llm_assessment = Column(JSONB, nullable=True)
    event_ids = Column(ARRAY(String), nullable=True)
    assigned_to = Column(UUID(as_uuid=True), nullable=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    analyst_verdict = Column(String(20), nullable=True)
    analyst_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Case(Base):
    """Investigation case grouping related alerts."""

    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_number = Column(Integer, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="open", index=True)
    severity = Column(String(20), nullable=False)
    domain = Column(String(100), nullable=False, index=True)
    assigned_to = Column(UUID(as_uuid=True), nullable=True)
    narrative_draft = Column(Text, nullable=True)
    narrative_approved = Column(Boolean, default=False)
    narrative_approved_by = Column(UUID(as_uuid=True), nullable=True)
    narrative_approved_at = Column(DateTime, nullable=True)
    narrative_status = Column(String(50), default="draft")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


class ChatSession(Base):
    """Chat session for user-assistant interaction."""

    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)


class ChatMessage(Base):
    """Individual chat message in a session."""

    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Report(Base):
    """Generated compliance or analysis report."""

    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(255), nullable=False)
    report_type = Column(String(50), nullable=False)
    content = Column(JSONB, nullable=False)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
