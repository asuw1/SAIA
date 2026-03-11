from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Rule(Base):
    """
    A compliance rule that maps to a regulatory clause.
    logic_json stored as JSONB for direct querying in PostgreSQL.
    Status lifecycle: draft → active → archived
    """
    __tablename__ = "rules"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    clause_id   = Column(Integer, ForeignKey("clauses.id"), nullable=False)
    severity    = Column(String(20), nullable=False)               # Critical | High | Medium | Low
    logic_json  = Column(JSONB, nullable=False)                    # rule conditions as JSONB
    version     = Column(String(20), default="1.0")
    status      = Column(String(20), default="draft")              # draft | active | archived
    author_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

    clause = relationship("Clause", back_populates="rules")
    alerts = relationship("Alert", back_populates="rule")
