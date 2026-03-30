"""Chatbot router for SAIA V4."""

from datetime import datetime, timezone, timedelta
from typing import Optional, AsyncGenerator
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user
from ..models.chat import (
    ChatMessage,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatHistoryResponse,
)
from ..models.base import ChatSession, ChatMessage as ChatMessageModel
from ..services.chatbot_service import classify_intent, handle_message
from ..services.llm_client import LLMClient
from ..services.rag_service import RAGService

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


async def sse_stream(
    content: str,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE (Server-Sent Events) stream.

    Args:
        content: Text content to stream

    Yields:
        SSE formatted data strings
    """
    words = content.split()
    for i, word in enumerate(words):
        chunk = word if i == 0 else " " + word
        yield f"data: {chunk}\n\n"

        if (i + 1) % 10 == 0:
            yield "data: \n\n"


@router.post(
    "/session",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat session",
    description="Create new chat session",
)
async def create_session(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ChatSessionResponse:
    """
    Create a new chat session.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        ChatSessionResponse with session ID
    """
    session_id = uuid4()

    new_session = ChatSession(
        id=session_id,
        user_id=current_user.get("user_id"),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    return ChatSessionResponse.model_validate(new_session)


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List sessions",
    description="List user's chat sessions",
)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[ChatSessionResponse]:
    """
    List chat sessions for the current user.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of ChatSessionResponse
    """
    user_id = current_user.get("user_id")
    offset = (page - 1) * page_size

    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.created_at))
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [ChatSessionResponse.model_validate(s) for s in sessions]


@router.get(
    "/sessions/{session_id}/history",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session history",
    description="Load chat history for a session",
)
async def get_history(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ChatHistoryResponse:
    """
    Get chat history for a session.

    Args:
        session_id: Chat session ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        ChatHistoryResponse with messages

    Raises:
        HTTPException: 404 if session not found, 403 if not owner
    """
    user_id = current_user.get("user_id")

    session_stmt = select(ChatSession).where(ChatSession.id == session_id)
    session_result = await db.execute(session_stmt)
    session = session_result.scalars().first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    now = datetime.now(timezone.utc)
    if session.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session has expired",
        )

    messages_stmt = (
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session_id)
        .order_by(ChatMessageModel.created_at)
    )

    messages_result = await db.execute(messages_stmt)
    messages = messages_result.scalars().all()

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
    )


@router.post(
    "/message",
    status_code=status.HTTP_200_OK,
    summary="Send message",
    description="Send message to chatbot (SSE streaming response)",
)
async def send_message(
    chat_msg: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    Send a message to the chatbot and get streaming response.

    Args:
        chat_msg: Chat message request
        db: Database session
        current_user: Current authenticated user

    Returns:
        StreamingResponse with Server-Sent Events

    Raises:
        HTTPException: 404 if session not found, 403 if not owner, 410 if expired
    """
    user_id = current_user.get("user_id")
    session_id = chat_msg.session_id

    session_stmt = select(ChatSession).where(ChatSession.id == session_id)
    session_result = await db.execute(session_stmt)
    session = session_result.scalars().first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    now = datetime.now(timezone.utc)
    if session.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session has expired",
        )

    user_message = ChatMessageModel(
        id=uuid4(),
        session_id=session_id,
        role="user",
        content=chat_msg.message,
        sources=None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(user_message)
    await db.commit()

    intent = classify_intent(chat_msg.message)

    llm_client = LLMClient()
    rag_service = RAGService()

    response_content = await handle_message(
        message=chat_msg.message,
        session_id=session_id,
        user_id=user_id,
        db=db,
        llm_client=llm_client,
        rag_service=rag_service,
    )

    assistant_message = ChatMessageModel(
        id=uuid4(),
        session_id=session_id,
        role="assistant",
        content=response_content,
        sources=None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(assistant_message)
    await db.commit()

    return StreamingResponse(
        sse_stream(response_content),
        media_type="text/event-stream",
    )
