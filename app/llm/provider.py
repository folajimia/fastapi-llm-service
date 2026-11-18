# class ProviderLLMClient:
#     async def generate(self, prompt: str) -> str:
#         # Call the provider SDK here.
#         # Later: call the selected provider SDK here.
#         # This file, not a route, owns that translation.
#         raise NotImplementedError

import httpx


class ProviderLLMClient:
    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://api.example.com/v1/generate",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "prompt": prompt},
            )
            response.raise_for_status()
            return response.json()["text"]
