"""Chat Pydantic schemas for SAIA V4."""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class ChatMessage(BaseModel):
    """Request model for sending a chat message."""

    session_id: UUID
    message: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    """Response model for a chat message."""

    id: UUID
    role: str = Field(..., description="user or assistant")
    content: str
    sources: Optional[list[dict]] = Field(
        None,
        description="Retrieved sources/context used for the response",
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    """Response model for a chat session."""

    session_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    """Response model for chat session history."""

    session_id: UUID
    messages: list[ChatMessageResponse]
