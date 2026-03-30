from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Role(Base):
    __tablename__ = "roles"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(50), unique=True, nullable=False)  # Admin | Auditor | Compliance Officer
    permissions = Column(JSONB, nullable=True)                     # list of allowed actions as JSONB

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(100), unique=True, nullable=False, index=True)
    email           = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name       = Column(String(200), nullable=True)
    role_id         = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login      = Column(DateTime, nullable=True)

    role       = relationship("Role", back_populates="users")
    alerts     = relationship("Alert", back_populates="assigned_user")
    audit_logs = relationship("AuditLog", back_populates="user")
