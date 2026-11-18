import anthropic

from app.llm.errors import LLMProviderError, LLMResponseValidationError, LLMTimeoutError


class AnthropicLLMClient:
    """Adapter: implements our LLMClient protocol using the Anthropic SDK.

    Only this file knows Anthropic exists. Everything else in the app
    still talks to the LLMClient protocol (the 06C boundary).
    """

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
        self._model = model

    async def generate(self, prompt: str) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APITimeoutError as error:
            raise LLMTimeoutError("the model did not answer in time") from error
        except anthropic.RateLimitError as error:
            raise LLMProviderError("rate limited by the provider") from error
        except anthropic.APIStatusError as error:
            raise LLMProviderError(f"provider error: {error.status_code}") from error
        except anthropic.APIConnectionError as error:
            raise LLMProviderError("could not reach the provider") from error

        # response.content is a *list of blocks* (text, thinking, tool_use, ...).
        # Find the text block — do not assume content[0].text exists.
        text = next(
            (block.text for block in response.content if block.type == "text"), None
        )
        if text is None:
            raise LLMResponseValidationError("the model returned no text block")
        return text
