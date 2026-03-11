from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class RoleOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: Optional[str]


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str
    role_id: int


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    role: RoleOut
    created_at: datetime
    model_config = {"from_attributes": True}
