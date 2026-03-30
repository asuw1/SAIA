"""JWT Authentication and RBAC middleware for SAIA V4."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Callable
from uuid import UUID
from fastapi import Request, HTTPException, Depends, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from ..config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """JWT token payload claims."""

    user_id: UUID
    role: str
    data_scope: list[str]
    exp: datetime


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(
    user_id: UUID, role: str, data_scope: list[str]
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: UUID of the user
        role: User role (Admin, Auditor, Compliance Officer)
        data_scope: List of domains the user has access to

    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=settings.jwt_expiration_minutes)

    payload = {
        "user_id": str(user_id),
        "role": role,
        "data_scope": data_scope,
        "exp": expiration.timestamp(),
        "iat": now.timestamp(),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    return token


def verify_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload with decoded claims

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = UUID(payload.get("user_id"))
        role = payload.get("role")
        data_scope = payload.get("data_scope", [])
        exp_timestamp = payload.get("exp")

        if not user_id or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        exp = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        return TokenPayload(
            user_id=user_id,
            role=role,
            data_scope=data_scope,
            exp=exp,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token format: {str(e)}",
        )


async def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency that extracts and validates the current user from the Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary with keys: user_id (UUID), role (str), data_scope (list[str])

    Raises:
        HTTPException: If Authorization header is missing or invalid
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract Bearer token
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    payload = verify_token(token)

    return {
        "user_id": payload.user_id,
        "role": payload.role,
        "data_scope": payload.data_scope,
    }


def require_roles(*allowed_roles: str) -> Callable:
    """
    FastAPI dependency factory that enforces role-based access control.

    Args:
        allowed_roles: One or more allowed user roles

    Returns:
        Async function that can be used as a FastAPI dependency

    Raises:
        HTTPException: If user's role is not in allowed_roles
    """

    async def check_role(current_user: dict = Depends(get_current_user)) -> dict:
        """Check if user has one of the allowed roles."""
        user_role = current_user.get("role")

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user_role}' is not authorized for this resource",
            )

        return current_user

    return check_role
