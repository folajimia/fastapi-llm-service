import uuid

from app.api.dependencies import get_chat_service
from app.services.chat import ChatService


class FakeLLMClient:
    async def generate(self, prompt: str) -> str:
        return "fake reply"


def test_chat_route_uses_injected_service(client):
    client.app.dependency_overrides[get_chat_service] = lambda: ChatService(
        llm_client=FakeLLMClient()
    )
    try:
        response = client.post("/api/v1/chat", json={"message": "Hello"})
        body = response.json()
        assert body["reply"] == "fake reply"
        assert uuid.UUID(body["conversation_id"])  # a valid UUID is returned
    finally:
        client.app.dependency_overrides.clear()
