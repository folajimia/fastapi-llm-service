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

**On this machine** — `poetry add` is blocked by the corporate proxy (the Lesson 07 quirk). The stopgap pattern is:

```bash
REQUESTS_CA_BUNDLE=~/.certs/corporate-cas.pem poetry run pip install httpx
```

(The same stopgap pattern applies to every `poetry add` in this course — e.g. `poetry add anthropic` in Step 4.)

One subtlety worth understanding: this pip command will likely print `Requirement already satisfied`, because httpx is **already installed as a dev dependency** — `TestClient` uses it. That is not the same as being a *main* dependency. The moment `app/llm/` (production code) imports httpx, it must be declared in the main dependency list — otherwise `poetry install --only main`, which is what the Docker image runs in Lesson 10, produces an environment **without** httpx and the app crashes on import. The pip stopgap fixes the installed state; the debt is the declared state. Pay everything off together on a clean network (this is the running debt list for the whole course — it grows as later lessons hit blocked `poetry add` commands, e.g. `anthropic` in Step 4, `structlog` in Lesson 09):

```bash
poetry add sqlalchemy alembic asyncpg pydantic-settings httpx anthropic
```

(`poetry add httpx` adds it to the main dependencies; it is currently also listed in the dev group in `pyproject.toml` — remove the dev-group line afterwards so it is not declared twice.)

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

**As built (2026-10-05):** the handlers live in `app/api/errors.py` behind a `register_exception_handlers(app)` function called once from `main.py` — same handlers, but importable without a circular import (`errors.py` cannot import `app` from `main.py`, because `main.py` imports `errors.py`). Verified live: the gateway's 401 came back to the client as a clean `502 {"detail": "The model provider failed."}` instead of a raw 500 with a stack trace leaking internal file paths.

## Step 4 — Connect a real LLM provider (worked example)

Step 2 showed the wiring pattern with generic httpx scaffolding. When you pick a real provider, use its **official SDK** instead of hand-rolled HTTP: you get typed error classes (no string matching on error messages), automatic retries of rate limits and server errors, and the SDK tracks API changes so your adapter does not rot.

For this project, the example provider is **Claude (Anthropic)**:

```bash
poetry add anthropic
```

**On this machine** — blocked by the corporate proxy (see the stopgap explanation in Step 2). Same pattern:

```bash
REQUESTS_CA_BUNDLE=~/.certs/corporate-cas.pem poetry run pip install anthropic
```

This adds `anthropic` to the debt list — it joins the payoff command in Step 2.

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

## Step 8 — See the real LLM in action (smoke test)

Fakes prove your *logic*. They cannot prove your *wiring* — the API key is real, the URL is real, the SDK version talks to the real service. A **smoke test** is one real call, on demand, never in the default test run. This step is the reward for the whole architecture: the moment a real Claude answer flows through your layers.

Two levels, run in order — direct first, then through the service:

| Level | What it proves | If it fails |
|---|---|---|
| Direct: call your adapter in a script | key, SDK, URL, adapter code | the problem is in the adapter/settings |
| Through the service: `curl` the running app | the whole route → service → adapter chain | the problem is in the wiring |

Isolating like this means a failure instantly tells you *which layer* to look at.

### Step 8a — Get a key (5 minutes, one time)

1. Before creating a personal key, check whether Zendesk already provides an internal LLM gateway or approved key — using a personal API key for work projects may be against policy, and an internal gateway is usually the right answer at a company.
2. Otherwise: create a key at `console.anthropic.com` (Settings → API keys). Keys look like `sk-ant-...`.
3. Put it in `.env` (untracked — never committed, never logged):

```text
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-key-here
LLM_MODEL=claude-opus-5
```

And copy the three *names* (no values) into `.env.example`.

**Cost note:** each call is billed per token. One short call is fractions of a cent — the reason for smoke tests is not the money, it is that **real calls never belong in the default test suite**, or CI pays on every push.

### Step 8b — Direct smoke test: your adapter, one call

A tiny script — not a test, just eyes on the result:

```python
# scripts/smoke_llm.py
import asyncio

from app.core.config import settings
from app.llm.anthropic_client import AnthropicLLMClient


async def main() -> None:
    client = AnthropicLLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
    )
    reply = await client.generate("Reply with exactly: the pipeline works")
    print("REAL LLM REPLY:", reply)


asyncio.run(main())
```

```bash
mkdir -p scripts
poetry run python scripts/smoke_llm.py
```

Expected: `REAL LLM REPLY: the pipeline works` (or close — it is a real model, exact wording is its choice).

**Verified on this machine (2026-10):** the app's Python verifies `api.anthropic.com` out of the box — no corporate-CA workaround needed. The proxy problem from Lesson 07 affects only Poetry (Homebrew OpenSSL); `api.anthropic.com` was tested and returns a clean `401` without a key, `200`-path with one. If this ever changes, the fix is the same `~/.certs/corporate-cas.pem` bundle from Lesson 07, passed to the SDK's HTTP client.

### Step 8c — Through the service: provider branch + curl

Make `get_chat_service` choose by settings, so the same codebase runs demo (tests, no key), anthropic, or the company gateway — **the final version as built**:

```python
# app/api/dependencies.py
from app.core.config import settings
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.client import LLMClient
from app.llm.gateway import GatewayLLMClient
from app.services.chat import ChatService


class DemoLLMClient:
    async def generate(self, prompt: str) -> str:
        return f"Demo response for: {prompt}"


def get_chat_service() -> ChatService:
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
    return ChatService(llm_client=client)
```

This function is the **composition root** — the only place concrete classes are chosen; everything else deals in the Protocol. See [[Lessons/11 Architecture Walkthrough|Lesson 11]] Part 4 Step 6 for the full explanation.

Then run the app and ask it something only a real model can answer:

```bash
poetry run uvicorn app.main:app --reload
curl -X POST localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "In one sentence, why is the sky blue?"}'
```

Expected: a real answer about light scattering — impossible for `DemoLLMClient`, which can only echo `"Demo response for: ..."`. That impossibility is what makes it a *proof*: the response could only have come through the full chain.

Set `LLM_PROVIDER=demo` in `.env` afterwards to go back to free local runs.

### Step 8d — A repeatable smoke test (skipped by default)

Script → curl is manual. This is the pytest version — the same idea, runnable on demand, and **skipped in every normal run**:

```python
# tests/smoke/test_real_llm.py
import asyncio
import os

import pytest

from app.core.config import settings
from app.llm.anthropic_client import AnthropicLLMClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("LLM_SMOKE") or not settings.llm_api_key,
    reason="set LLM_SMOKE=1 and provide LLM_API_KEY to run real (paid) LLM calls",
)


def test_real_llm_answers() -> None:
    client = AnthropicLLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
    )

    reply = asyncio.run(client.generate("Reply with exactly: smoke test passed"))

    # A real model is not deterministic — assert SHAPE, not content.
    assert isinstance(reply, str)
    assert reply.strip() != ""
```

```bash
mkdir -p tests/smoke
touch tests/smoke/__init__.py

poetry run pytest -q                        # normal run: the smoke test is SKIPPED (s)
LLM_SMOKE=1 poetry run pytest tests/smoke -v   # explicit run: makes one real call
```

Read the design decisions:

- **The `LLM_SMOKE=1` gate** — real calls happen only when you explicitly ask. A plain `poetry run pytest` (and CI) can never spend money by accident. The skip reason prints *why* it was skipped.
- **Assertions check shape, not content** — `isinstance(reply, str)` and non-empty, not an exact sentence. A real model answers slightly differently every run; asserting exact text would make the test flaky for no reason. This is exactly why *logic* tests use fakes and *smoke* tests stay tiny: fakes are deterministic and can assert anything; real calls can only prove "it worked at all."

### What smoke tests are for (and not for)

| | Fake tests (Steps 5–7) | Smoke test (this step) |
|---|---|---|
| Proves | your logic: prompts, retries, error mapping | your wiring: key, SDK, URL, integration |
| Deterministic | yes | no |
| Cost | free | paid, per run |
| In the default suite | yes | **never** |

Neither replaces the other. The fake suite says "the code is right"; the smoke test says "the plumbing is right." You need both.

### Step 8e — The real provider: Zendesk's internal AI gateway (verified 2026-10-05)

Zendesk provides an internal LLM gateway (`https://ai-gateway.zende.sk/bedrock`) that speaks the Anthropic Messages API over HTTPS with bearer-token auth. No personal API key needed. Integration contract, from the gateway docs' curl:

```bash
curl "${AWS_ENDPOINT_URL_BEDROCK_RUNTIME}/model/global.anthropic.claude-sonnet-5/invoke" \
  -H "Authorization: Bearer ${AWS_BEARER_TOKEN_BEDROCK}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":[{"type":"text","text":"..."}]}],"anthropic_version":"bedrock-2023-05-31","max_tokens":256}'
```

Mapping to settings — the two shell exports become `.env` lines (Lesson 05's one-source-of-truth rule):

| curl piece | Setting |
|---|---|
| `${AWS_ENDPOINT_URL_BEDROCK_RUNTIME}` | `llm_base_url` |
| `Bearer $TOKEN` | `llm_api_key` |
| `global.anthropic.claude-sonnet-5` | `llm_model` |
| `LLM_PROVIDER` | `"gateway"` |

```text
# .env
LLM_PROVIDER=gateway
LLM_BASE_URL=https://ai-gateway.zende.sk/bedrock
LLM_API_KEY=<the bearer token>
LLM_MODEL=global.anthropic.claude-sonnet-5
```

The adapter is `app/llm/gateway.py` — the Step 2 httpx scaffolding made real, with the Step 3 domain-error mapping. It is the only file that knows the gateway's URL shape, auth header, and `anthropic_version` value. Smoke ladder, cheapest first: the curl (gateway works) → `scripts/smoke_llm.py` (adapter works) → `curl` through the app (chain works).

**Response shape, confirmed live** (this is what `InvokeModel` returns for Claude models):

```json
{"type": "message",
 "content": [{"type": "text", "text": "..."}],
 "stop_reason": "max_tokens",
 "usage": {"input_tokens": 12, "output_tokens": 256}}
```

Three fields the adapter reads — and one to watch:

- `content` → the text blocks the adapter extracts.
- `stop_reason` → `"max_tokens"` means the reply was **cut off mid-sentence** (the docs' `max_tokens: 256` example truncates visibly). A production adapter logs or flags this instead of silently returning a chopped answer — Lesson 09's logging is where that lands.
- `usage` → input/output token counts; the raw material of cost tracking.

No TLS workaround needed: the app's Python verifies the gateway out of the box (the corporate-CA problem from Lesson 07 affects only Poetry's Homebrew OpenSSL).

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
- [ ] A direct smoke call to the adapter returned a real reply (Step 8b).
- [ ] The full chain returned a real reply via `curl` with `LLM_PROVIDER=anthropic` (Step 8c).
- [ ] A smoke pytest test exists, is **skipped in every normal run**, and runs only with `LLM_SMOKE=1` (Step 8d).

## Mentor questions

1. Which failures are retryable — and who decides, the adapter or the caller?
2. Where should prompt templates live? (Hint: a `prompts.py` next to the service, or the service itself — what changes when prompts change?)
3. What is the correct API response when output validation fails — 502, or 200 with a partial result?

## Progress

- Status: **In progress — errors and adapters exist; retry integration and structured workflow remain**
- Completed: [x] timeout/error types [x] provider adapters [x] HTTP error mapping [ ] retry integration [ ] structured-output endpoint [ ] complete failure-test matrix
- Date:

## References

[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) · [FastAPI — Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/) · [httpx — Quickstart](https://www.python-httpx.org/quickstart/) · [Pydantic — Validation](https://docs.pydantic.dev/latest/concepts/validation/)

## Review note

This lesson explains the reliability design, but the repository is not yet at the checkpoint. Domain errors and provider timeouts exist; retry integration, structured-output endpoint wiring, and the full failure-test matrix remain implementation tasks. Treat each unchecked item as a separate exercise rather than assuming the examples are already live.
