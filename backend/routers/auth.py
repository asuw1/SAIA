"""Authentication router for SAIA V4."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ..database import get_db
from ..middleware.auth import (
    get_current_user,
    require_roles,
    hash_password,
    verify_password,
    create_access_token,
)
from ..models.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
)
from ..models.base import User

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user and return JWT access token",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user with username and password.

    Args:
        request: Login credentials
        db: Database session

    Returns:
        LoginResponse with access token and user info

    Raises:
        HTTPException: 401 if credentials invalid, 404 if user not found
    """
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
        data_scope=user.data_scope or ["*"],
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create new user account (Admin only)",
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("Admin")),
) -> UserResponse:
    """
    Register a new user (Admin only).

    Args:
        request: Registration details
        db: Database session
        current_user: Current authenticated user (must be Admin)

    Returns:
        UserResponse with new user details

    Raises:
        HTTPException: 409 if username already exists, 403 if not admin
    """
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    password_hash = hash_password(request.password)

    new_user = User(
        username=request.username,
        password_hash=password_hash,
        role=request.role,
        data_scope=request.data_scope or ["*"],
        is_active=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Retrieve authenticated user's profile information",
)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Get the current authenticated user's profile.

    Args:
        current_user: Current authenticated user from JWT token
        db: Database session

    Returns:
        UserResponse with user details
    """
    user_id = current_user.get("user_id")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)
