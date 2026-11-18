import httpx

from app.llm.errors import LLMProviderError, LLMResponseValidationError, LLMTimeoutError


class GatewayLLMClient:
    """Adapter for Zendesk's internal AI gateway (Bedrock Runtime protocol).

    The only file that knows the gateway's URL shape, auth header,
    and request/response formats. Implements the LLMClient protocol
    by shape — an async generate(prompt) -> str.
    """

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str) -> str:
        url = f"{self._base_url}/model/{self._model}/invoke"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ],
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 16000,  # generous cap — hitting it truncates mid-sentence
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("the model did not answer in time") from error
        except httpx.HTTPStatusError as error:
            raise LLMProviderError(
                f"gateway error: {error.response.status_code}"
            ) from error
        except httpx.HTTPError as error:
            raise LLMProviderError("could not reach the gateway") from error

        data = response.json()
        text = next(
            (
                block["text"]
                for block in data.get("content", [])
                if block.get("type") == "text"
            ),
            None,
        )
        if text is None:
            raise LLMResponseValidationError("the model returned no text block")
        return text
