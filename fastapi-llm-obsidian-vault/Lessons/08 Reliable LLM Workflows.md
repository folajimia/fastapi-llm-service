# Lesson 08 — Reliable LLM Workflows

## Objective

Turn the LLM call from "hopefully it answers" into a production-grade step: explicit timeouts, retry only where it is safe, typed errors, and validated structured output.

## The idea in simple terms

A **demo** assumes the provider answers in two seconds and always returns what you expect. A **service** assumes the network will fail, the provider will rate-limit you, and the model will sometimes return garbage. Every line of this lesson is written for that second world.

Workflow shape:

```text
input → validation → prompt → model (timeout, retry) → response validation → business rules → output
```

Start with explicit workflows such as `summarize`, `extract`, or `classify`. Do not build an autonomous agent until the product genuinely requires one.

## Step 1 — Add LLM settings

Extend `Settings` in `app/core/config.py` (names only in `.env.example`; the real values live in untracked `.env`):

```python
llm_provider: str = "demo"            # which adapter to build
llm_api_key: str = ""                 # secret — never commit, never log
llm_model: str = "some-model"
llm_timeout_seconds: float = 30.0
llm_max_retries: int = 2
```

## Step 2 — Provider adapter scaffolding

Replace the stub in `app/llm/provider.py` with a real adapter. Using `httpx` directly keeps this lesson provider-agnostic:

```bash
poetry add httpx
```

```python
# app/llm/provider.py
import httpx

from app.core.config import settings


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
```

Then `get_chat_service` in `app/api/dependencies.py` builds it from settings — `DemoLLMClient` finally retires:

```python
def get_chat_service() -> ChatService:
    client: LLMClient = ProviderLLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
    )
    return ChatService(llm_client=client)
```

`httpx.AsyncClient(timeout=...)` gives you the timeout for free — that single argument is the difference between "the request hangs forever and takes the worker with it" and "the request fails in 30 seconds with an exception you can handle."

## Step 3 — Define your own error types

The service should speak in **domain errors**, not provider errors. Create `app/llm/errors.py`:

```python
class LLMError(Exception):
    """Base class for all LLM-related failures."""


class LLMTimeoutError(LLMError):
    """The provider did not answer within the timeout."""


class LLMProviderError(LLMError):
    """The provider answered with an error (rate limit, 5xx, auth...)."""


class LLMResponseValidationError(LLMError):
    """The provider answered, but the answer was not valid for our workflow."""
```

Then the **route layer** translates them into HTTP status codes. This answers mentor question 2 from [[Lessons/06 Service Boundaries and LLM Client|Lesson 06]]: the service *raises* domain errors; the route (via FastAPI exception handlers) *translates*:

```python
# app/main.py (or a dedicated app/api/errors.py)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.llm.errors import LLMError, LLMProviderError, LLMResponseValidationError, LLMTimeoutError


@app.exception_handler(LLMTimeoutError)
async def timeout_handler(request: Request, exc: LLMTimeoutError) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": "The model did not respond in time."})


@app.exception_handler(LLMProviderError)
async def provider_handler(request: Request, exc: LLMProviderError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "The model provider failed."})


@app.exception_handler(LLMResponseValidationError)
async def validation_handler(request: Request, exc: LLMResponseValidationError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "The model returned an invalid response."})
```

Why 502/504 and not 500: 5xx means "I broke"; 502/504 mean "a system I depend on broke or was too slow." Your monitoring and your callers can tell the difference.

## Step 4 — Connect a real LLM provider (worked example)

Step 2 showed the wiring pattern with generic httpx scaffolding. When you pick a real provider, use its **official SDK** instead of hand-rolled HTTP: you get typed error classes (no string matching on error messages), automatic retries of rate limits and server errors, and the SDK tracks API changes so your adapter does not rot.

For this project, the example provider is **Claude (Anthropic)**:

```bash
poetry add anthropic
```

```python
# app/llm/anthropic_client.py
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
```

Read this against everything before it:

- It satisfies the `LLMClient` protocol **by shape** — an async `generate(prompt) -> str` — without inheriting from anything. That is the structural-typing idea from [[Lessons/06A ChatService Without FastAPI|06A]] paying off: one new file, zero changes to the service or routes.
- The `except` chain goes **most specific first** (`APITimeoutError` before the broad `APIConnectionError`), and every branch maps an SDK exception to one of *your* domain errors from Step 3 — with `from error` preserving the cause chain for debugging. The service and routes never see an Anthropic-specific exception.
- The timeout is set once, on the client, in the constructor — not repeated at every call site.
- `max_tokens` is deliberately generous: hitting the cap truncates the reply mid-sentence. Tune it down when you have a real reason (cost, latency), not by reflex.

Wire it in `app/api/dependencies.py` — same wiring as Step 2, different adapter:

```python
from app.llm.anthropic_client import AnthropicLLMClient


def get_chat_service() -> ChatService:
    client: LLMClient = AnthropicLLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,        # e.g. LLM_MODEL=claude-opus-5 in .env
        timeout=settings.llm_timeout_seconds,
    )
    return ChatService(llm_client=client)
```

Secret handling, in one list:

- `LLM_API_KEY` lives in `.env` (untracked); `.env.example` carries the *name only*.
- Never log it, never put it in a URL, never bake it into a Docker image (Lesson 10's `.dockerignore` line for `.env` exists partly for this).
- The SDK also reads `ANTHROPIC_API_KEY` from the environment automatically if you construct `AsyncAnthropic()` with no arguments — passing it explicitly from `Settings` keeps all configuration in one place, which is easier to reason about while learning.

And the payoff of all the boundary work: connecting a real provider changed **one new file plus three lines of wiring**. No test touches the network (they keep injecting fakes from 06D), and `DemoLLMClient` remains available for manual smoke runs by keeping a `llm_provider=demo` setting branch in the wiring.

One more thing before writing your own retry loop (next step): the Anthropic SDK **already retries** 429s, 5xx, and connection errors automatically with exponential backoff (default 2 attempts). Always check what your SDK provides before layering your own retries on top — the next step's loop is for when you need control beyond the default.

## Step 5 — Retry only what is safe to retry

The rule, in one line: **retry flakiness, never retry mistakes.**

- Retry: timeouts, 429 rate limit (after waiting), 5xx server errors.
- Do not retry: 400/401/403 — a bad request or bad key fails identically every time; retrying just fails three times slower.

A retry loop with backoff (each attempt waits longer, so you do not hammer a struggling provider):

```python
import asyncio

from app.llm.errors import LLMProviderError, LLMTimeoutError


async def generate_with_retry(client: LLMClient, prompt: str, max_retries: int) -> str:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await client.generate(prompt)
        except (LLMTimeoutError, LLMProviderError) as error:
            last_error = error
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (2**attempt))  # 0.5s, 1s, 2s...
    assert last_error is not None
    raise last_error
```

Where does this live? In the adapter or a small helper the service uses — not in the route. Retrying is workflow logic, not HTTP logic.

## Step 6 — One structured-output workflow

Add a workflow endpoint, e.g. `POST /api/v1/extract` — "pull a structured person out of free text". Treat model output as **untrusted input**, exactly like user input:

```python
# app/schemas/extract.py
from pydantic import BaseModel


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class ExtractedPerson(BaseModel):
    name: str
    occupation: str | None = None
    country: str | None = None
```

In the workflow, ask the model for JSON, then validate it:

```python
from pydantic import ValidationError

from app.llm.errors import LLMResponseValidationError


async def extract_person(self, text: str) -> ExtractedPerson:
    prompt = (
        "Extract the person from the text as JSON with keys "
        "'name', 'occupation', 'country'. Reply with JSON only.\n"
        f"Text: {text}"
    )
    raw = await self._llm_client.generate(prompt)
    try:
        return ExtractedPerson.model_validate_json(raw)
    except ValidationError as error:
        raise LLMResponseValidationError(str(error)) from error
```

`raise ... from error` keeps the original cause attached — when you debug, you see the whole chain.

## Step 7 — Test every failure with fakes

No network, no mocks library — just small fakes, same pattern as [[Lessons/06D Testing the ChatService|06D]]:

```python
class TimeoutClient:
    async def generate(self, prompt: str) -> str:
        raise LLMTimeoutError("simulated timeout")


class FlakyClient:
    """Fails twice, then succeeds — proves the retry loop works."""
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.calls < 3:
            raise LLMProviderError("simulated 503")
        return "ok"


class GarbageClient:
    async def generate(self, prompt: str) -> str:
        return "this is not json"
```

Tests worth writing:

- `FlakyClient` + retry helper → result is `"ok"` and `calls == 3`.
- `TimeoutClient` → the route test asserts a **504** response (via `TestClient`).
- `GarbageClient` + `extract_person` → raises `LLMResponseValidationError`, route returns 502.
- Non-retryable error (e.g. auth) → exactly one call, no retry.

## Reliability rules

- Set explicit timeouts — always, on every external call.
- Retry only failures that are safe to retry.
- Map provider failures to application errors; let exception handlers do the HTTP translation.
- Validate model output before passing it anywhere.
- Never log API keys or sensitive prompt content.

## Common mistakes

- **No timeout at all** — a hanging provider quietly eats your workers.
- **Retrying a 400** — deterministic failure, retried deterministically.
- **Retrying without backoff** — three instant retries during an outage are three dropped requests.
- **Trusting model output** — a model that says `"Sure! Here's the JSON: {...}"` will break naive `json.loads`.
- **Catching every exception** (`except Exception`) somewhere deep — it hides real bugs. Catch the errors you defined.

## Checkpoint

- [ ] `Settings` carries provider, key, model, timeout, retries; `.env.example` has the names.
- [ ] A real provider adapter exists in its own file (`anthropic_client.py`), is the **only** file importing that SDK, and maps SDK errors to domain errors.
- [ ] The adapter is wired in `get_chat_service`; `DemoLLMClient` remains only as a settings-selected fallback for smoke runs.
- [ ] The API key appears in `.env` only — never in code, logs, or `.env.example` values.
- [ ] Domain errors exist in `app/llm/errors.py`; exception handlers map them to 502/504.
- [ ] Retry with backoff exists (or the SDK's built-in retries were evaluated and documented) and only retries safe failures.
- [ ] One structured-output workflow validates model output with a Pydantic model.
- [ ] Tests cover: success, timeout, retry-then-success, invalid output, non-retryable error — all with fakes.

## Mentor questions

1. Which failures are retryable — and who decides, the adapter or the caller?
2. Where should prompt templates live? (Hint: a `prompts.py` next to the service, or the service itself — what changes when prompts change?)
3. What is the correct API response when output validation fails — 502, or 200 with a partial result?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

## References

[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) · [FastAPI — Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/) · [httpx — Quickstart](https://www.python-httpx.org/quickstart/) · [Pydantic — Validation](https://docs.pydantic.dev/latest/concepts/validation/)
