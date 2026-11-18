# from app.llm.client import LLMClient


# class ChatService:
#     def __init__(self, llm_client: LLMClient) -> None:
#         self._llm_client = llm_client

#     async def reply(
#         self, user_message: str, conversation_id: uuid.UUID | None
#     ) -> str:
#     if conversation_id is None and self._repository is not None:
#         conversation = await self._repository.create_conversation()
#         conversation_id = conversation.id
#     await self._repository.add_message(conversation_id, "user", user_message)
#     prompt = self._build_prompt(user_message)
#     reply = await self._llm_client.generate(prompt)
#     await self._repository.add_message(conversation_id, "assistant", reply)
#     return reply

#     @staticmethod
#     def _build_prompt(user_message: str) -> str:
#         return f"You are a helpful assistant.\nUser: {user_message}"

from __future__ import annotations

import re
import uuid

from app.db.models import Message
from app.llm.client import LLMClient
from app.repositories.chat import ChatRepository
from app.repositories.memory import MemoryRepository

_NAME_PATTERNS = [
    re.compile(r"\bmy name is ([A-Za-z]+)\b", re.IGNORECASE),
    re.compile(r"\bcall me ([A-Za-z]+)\b", re.IGNORECASE),
]

def extract_facts(message: str) -> dict[str, str]:
    for pattern in _NAME_PATTERNS:
        if match := pattern.search(message):
            return {"name": match.group(1).capitalize()}
    return {}


class ChatService:
    def __init__(
        self,
        llm_client: LLMClient,
        repository: ChatRepository | None = None,
        memory: MemoryRepository | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._repository = repository
        self._memory = memory

    async def reply(
        self, user_message: str, conversation_id: uuid.UUID | None = None
    ) -> tuple[str, uuid.UUID]:
        conversation_id = await self._ensure_conversation(conversation_id)

        history: list[Message] = []
        if self._repository is not None:
            await self._repository.add_message(conversation_id, "user", user_message)
            history = await self._repository.get_history(conversation_id)

        facts = None

        # if self._memory is not None:
        #     for key, value in extract_facts(user_message).items():
        #         await self._memory.set_fact(key, value)
        #     facts = await self._memory.get_all()
        # else:
        #     facts = None

        prompt = self._build_prompt(user_message, history[:-1], facts)
        reply = await self._llm_client.generate(prompt)

        if self._repository is not None:
            await self._repository.add_message(conversation_id, "assistant", reply)

        return reply, conversation_id
    
    
    async def _ensure_conversation(
        self, conversation_id: uuid.UUID | None
    ) -> uuid.UUID:
        if conversation_id is not None:
            return conversation_id
        if self._repository is None:
            # No persistence configured — hand back a throwaway id so the
            # caller's contract (a conversation_id is always returned) holds.
            return uuid.uuid4()
        conversation = await self._repository.create_conversation()
        return conversation.id

        

    @staticmethod
    def _build_prompt(user_message: str,
        history: list[Message],
        facts: dict[str, str] | None = None,
    ) -> str:
        lines = ["You are a helpful assistant."]
        if facts:
            known = ", ".join(f"{key} is {value}" for key, value in sorted(facts.items()))
            lines.append(f"What you know about the user: {known}.")
        for message in history:
            lines.append(f"{message.role.capitalize()}: {message.content}")
        lines.append(f"User: {user_message}")
        return "\n".join(lines)
