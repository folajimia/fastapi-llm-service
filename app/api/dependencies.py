from app.llm.client import LLMClient
from app.services.chat import ChatService


class DemoLLMClient:
    async def generate(self, prompt: str) -> str:
        return f"Demo response for: {prompt}"

def get_chat_service() -> ChatService:
    client: LLMClient = DemoLLMClient()
    return ChatService(llm_client=client)