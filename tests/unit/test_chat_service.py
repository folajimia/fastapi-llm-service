import asyncio

from app.services.chat import ChatService


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_chat_service_returns_llm_response() -> None:
    fake_client = FakeLLMClient(response="Hello from the fake model")
    service = ChatService(llm_client=fake_client)

    result = asyncio.run(service.reply("Hello"))

    assert result == "Hello from the fake model"
    assert fake_client.prompts == [
        "You are a helpful assistant.\nUser: Hello"
    ]

def test_chat_service_propagates_provider_failure() -> None:
    class FailingClient:
        async def generate(self, prompt: str) -> str:
            raise RuntimeError("simulated provider failure")

    service = ChatService(llm_client=FailingClient())

    try:
        asyncio.run(service.reply("Hello"))
    except RuntimeError as error:
        assert str(error) == "simulated provider failure"
    else:
        raise AssertionError("Expected the provider failure")
