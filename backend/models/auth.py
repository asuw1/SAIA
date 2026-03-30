"""Authentication Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """Response model for user information."""

    id: UUID
    username: str
    role: str
    data_scope: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Response model for successful login."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    role: str = Field(..., description="User role: Admin, Auditor, or Compliance Officer")
    data_scope: list[str] = Field(default_factory=lambda: ["*"], description="Data scope domains")


class TokenPayload(BaseModel):
    """JWT token payload claims."""

    user_id: UUID
    role: str
    data_scope: list[str]
    exp: datetime
