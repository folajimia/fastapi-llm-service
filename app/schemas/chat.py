import uuid
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    conversation_id: Optional[uuid.UUID] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: uuid.UUID
