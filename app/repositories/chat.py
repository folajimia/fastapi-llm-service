import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self) -> Conversation:
        conversation = Conversation()
        self._session.add(conversation)
        await self._session.commit()
        return conversation

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: str
    ) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self._session.add(message)
        await self._session.commit()
        return message

    async def get_history(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars())
