# One real LLM call through the adapter — run manually, not in the test suite.
# Requires the provider settings in .env (LLM_PROVIDER, LLM_API_KEY, ...).
import asyncio

from app.core.config import settings
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.client import LLMClient
from app.llm.gateway import GatewayLLMClient


async def main() -> None:
    client: LLMClient
    if settings.llm_provider == "gateway":
        client = GatewayLLMClient(
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
        raise SystemExit(
            f"provider '{settings.llm_provider}' is not smoke-testable — "
            "set LLM_PROVIDER=gateway (or anthropic) in .env"
        )

    reply = await client.generate("Reply with exactly: the pipeline works")
    print("REAL LLM REPLY:", reply)


asyncio.run(main())
