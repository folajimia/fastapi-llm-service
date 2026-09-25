from app.llm.client import LLMClient


class ChatService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def reply(self, user_message: str) -> str:
        prompt = self._build_prompt(user_message)
        return await self._llm_client.generate(prompt)

    @staticmethod
    def _build_prompt(user_message: str) -> str:
        return f"You are a helpful assistant.\nUser: {user_message}"