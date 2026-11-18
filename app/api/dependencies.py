from typing import Annotated

from app.repositories.memory import MemoryRepository
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionFactory
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.client import LLMClient
from app.llm.gateway import GatewayLLMClient
from app.repositories.chat import ChatRepository
from app.services.chat import ChatService


class DemoLLMClient:
    async def generate(self, prompt: str) -> str:
        return f"Demo response for: {prompt}"


async def get_session() -> AsyncSession:
    async with SessionFactory() as session:
        yield session


async def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatService:
    if settings.llm_provider == "gateway":
        client: LLMClient = GatewayLLMClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    elif settings.llm_provider == "anthropic":
        client = AnthropicLLMClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    else:
        client = DemoLLMClient()
    return ChatService(llm_client=client, repository=ChatRepository(session), memory=MemoryRepository(session),)
