import asyncio
import uuid
from types import SimpleNamespace

from app.services.chat import ChatService


class RecordingFakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "ok"


class FakeRepository:
    """In-memory stand-in for ChatRepository — no database needed."""

    def __init__(self) -> None:
        self._messages: dict[uuid.UUID, list[SimpleNamespace]] = {}

    async def create_conversation(self) -> SimpleNamespace:
        conversation_id = uuid.uuid4()
        self._messages[conversation_id] = []
        return SimpleNamespace(id=conversation_id)

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: str
    ) -> None:
        self._messages[conversation_id].append(
            SimpleNamespace(role=role, content=content)
        )

    async def get_history(self, conversation_id: uuid.UUID) -> list[SimpleNamespace]:
        return list(self._messages[conversation_id])


class FakeMemory:
    """In-memory stand-in for MemoryRepository — a dict behind the same interface."""

    def __init__(self) -> None:
        self._facts: dict[str, str] = {}

    async def get_all(self) -> dict[str, str]:
        return dict(self._facts)

    async def set_fact(self, key: str, value: str) -> None:
        self._facts[key] = value


def test_name_is_injected_into_later_prompts() -> None:
    llm = RecordingFakeLLM()
    service = ChatService(
        llm_client=llm, repository=FakeRepository(), memory=FakeMemory()
    )

    reply, conversation_id = asyncio.run(service.reply("Hi, my name is Jimi"))
    asyncio.run(service.reply("What is my name?", conversation_id))

    assert "my name is Jimi" in llm.prompts[0]
    assert "name is Jimi" in llm.prompts[1]  # ← the whole lesson in one assertion
    assert conversation_id is not None


def test_service_without_memory_still_builds_prompts() -> None:
    llm = RecordingFakeLLM()
    service = ChatService(llm_client=llm, repository=FakeRepository())

    asyncio.run(service.reply("Hi, my name is Jimi"))

    assert "What you know about the user" not in llm.prompts[0]
