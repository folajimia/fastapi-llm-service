# Lesson 11 — Architecture Walkthrough: How It All Ties Together

> **Goal of this lesson:** read it once, understand every file in the project, and be able to explain the system to someone else — a mentor, a teammate, an interviewer — without notes.

Everything here describes the code **as it actually exists** (verified 2026-10-05, the day the first real LLM reply came through the full chain).

---

## Part 1 — The 30-second version (memorize this)

> "It's a FastAPI service where HTTP routes contain no business logic. Each route hands work to a `ChatService`, which owns the LLM workflow. The service talks to two things through interfaces, not concrete classes: an `LLMClient` protocol (so we can swap demo, Anthropic, or the company gateway with one config line) and a repository (so persistence is testable). Configuration flows from `.env` through one typed `Settings` object, and provider failures are translated into clean HTTP responses by exception handlers. Tests use fakes for logic and a gated smoke test for the real wiring."

If you can say that in your own words, you understand the system. The rest of this lesson is the proof, layer by layer.

---

## Part 2 — The architecture

```text
                     ┌────────────────────────────────────────────┐
 HTTP request        │                  FastAPI app               │
 ──────────────────► │  main.py → api/router.py → api/routes/     │
                     │        │                                   │
                     │        ▼  Depends()                       │
                     │  api/dependencies.py   ← builds objects    │
                     │        │                                   │
                     │        ▼                                   │
                     │  services/chat.py      ← business logic    │
                     │     │        │                             │
                     │     │        └── llm/client.py (Protocol)   │
                     │     │                 │  by shape:          │
                     │     │        ┌──────────┼──────────┐         │
                     │     │   llm/gateway.py  llm/anthropic_client.py
                     │     │   (Zendesk AI   │  (direct Anthropic) │
                     │     │    gateway)     │                     │
                     │     ▼                                   │
                     │  repositories/chat.py ← SQL only        │
                     │     │                                   │
                     │     ▼                                   │
                     │  db/session.py + db/models.py           │
                     │     │                                   │
                     └─────┼───────────────────────────────────┘
                           ▼
                  PostgreSQL (podman container)
```

The three sentences that describe every arrow:

1. **Routes only speak HTTP.** They validate, delegate, and wrap. No business logic, no SQL, no SDK imports.
2. **The service only speaks business.** "Build a prompt, call the LLM, save both sides." It never sees HTTP or SQL.
3. **Adapters and repositories only speak to the outside world.** Each is the single file allowed to know one external system exists.

## Part 3 — The file map (what lives where, and why)

```text
app/
├── main.py                    # the FastAPI app: router + exception handlers
├── core/
│   └── config.py              # Settings — the ONE place that reads .env
├── api/
│   ├── router.py              # collects route modules under /api/v1
│   ├── dependencies.py        # builds ChatService per request (provider choice)
│   ├── errors.py              # translates domain errors → HTTP status codes
│   └── routes/
│       ├── health.py          # GET /health (liveness)
│       └── chat.py            # POST /chat — validate, delegate, wrap
├── schemas/
│   ├── chat.py                # ChatRequest / ChatResponse (HTTP contracts)
│   └── extract.py             # structured-output workflow schemas
├── services/
│   └── chat.py                # ChatService — the workflow conductor
├── llm/
│   ├── client.py              # LLMClient Protocol — the promise list
│   ├── errors.py              # domain errors (LLMTimeoutError, ...)
│   ├── gateway.py             # adapter: Zendesk AI gateway  ◄── live in prod
│   ├── anthropic_client.py    # adapter: direct Anthropic SDK  (backup)
│   └── provider.py            # httpx scaffolding from Lesson 08 Step 2
├── db/
│   ├── base.py                # DeclarativeBase — models register here
│   ├── session.py             # async engine + session factory
│   └── models.py              # Conversation, Message tables
└── repositories/
    └── chat.py                # ChatRepository — the only SQL in the app
migrations/                    # Alembic: version control for the schema
tests/                         # unit (fast, fake) / api (TestClient) / smoke (real, gated)
scripts/smoke_llm.py           # one real LLM call, on demand
```

**The naming tells you the layer.** If you can name which folder a file belongs in, you know which rules apply to it. That is the whole point of the structure: the folder boundaries *are* the architecture.

---

## Part 4 — The life of a request (follow one curl through the system)

```bash
curl -X POST localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "How to center a div?"}'
```

### Step 1 — The edge: `app/main.py`

```python
app = FastAPI(title="LLM Services", version="0.1.0")
app.include_router(api_router, prefix="/api/v1")
register_exception_handlers(app)
```

Three lines, three jobs: create the app, mount all routes under `/api/v1` (versioning from Lesson 03 — clients pin to a version, so you can add `/api/v2` later without breaking anyone), and arm the error translators. Uvicorn receives the raw TCP bytes and hands FastAPI this `app` object.

### Step 2 — Routing and validation: `app/api/routes/chat.py`

```python
@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    reply = await service.reply(request.message)
    return ChatResponse(reply=reply)
```

Read this as four moves:

1. **`request: ChatRequest`** — FastAPI parses the JSON body into a Pydantic model *before your code runs*. `"message"` must be a string of 1–2000 chars (`schemas/chat.py`); anything else returns a 422 automatically, with zero validation code written by us.
2. **`service: ChatService = Depends(get_chat_service)`** — dependency injection. FastAPI calls `get_chat_service()` (see Step 6) and hands its return value here. The route never constructs a service or knows which LLM client it will get.
3. **`reply = await service.reply(...)`** — the *only* business call in the file. `await` because `reply` is async: the event loop is free to serve other requests while we wait on the LLM.
4. **`return ChatResponse(reply=reply)`** — the response model guarantees the JSON shape; FastAPI serializes it and returns 200.

If you memorize one sentence: **a route is a translator between HTTP and the service, nothing more.**

### Step 3 — The workflow conductor: `app/services/chat.py`

```python
class ChatService:
    def __init__(
        self,
        llm_client: LLMClient,
        repository: ChatRepository | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._repository = repository

    async def reply(
        self, user_message: str, conversation_id: uuid.UUID | None = None
    ) -> str:
        if self._repository is not None:
            if conversation_id is None:
                conversation = await self._repository.create_conversation()
                conversation_id = conversation.id
            await self._repository.add_message(conversation_id, "user", user_message)

        prompt = self._build_prompt(user_message)
        reply = await self._llm_client.generate(prompt)

        if self._repository is not None:
            await self._repository.add_message(conversation_id, "assistant", reply)
        return reply
```

Four things to be able to explain:

- **Dependencies arrive in the constructor.** The service does not create its own LLM client — the caller supplies one. That single decision is what makes the fakes in tests possible (Part 7).
- **The persistence is optional** (`if self._repository is not None`). No repository → the chat still works, it just isn't saved. This is why old tests pass unchanged.
- **Order matters:** the user's message is saved *before* the LLM call, the reply *after*. If the LLM fails, the user's message is still recorded — an audit trail of what was asked even when the answer never came.
- **`from __future__ import annotations`** (first line) makes type hints lazy, which is how the modern `uuid.UUID | None` syntax runs on this project's Python 3.9.

Prompt building lives here (`_build_prompt`), not in the route — prompts are business logic, the service's most valuable secret.

### Step 4 — The boundary promise: `app/llm/client.py`

```python
class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
```

This is the entire interface — four lines. `Protocol` means: *any object with this method shape IS an LLMClient*, no inheritance required. The service's type hint promises only "something that can generate." Everything downstream is built on this idea:

| Implementation | File | Satisfies the protocol by |
|---|---|---|
| `DemoLLMClient` | `api/dependencies.py` | echoes a fixed string — tests, free local runs |
| `AnthropicLLMClient` | `llm/anthropic_client.py` | the real Anthropic SDK |
| `GatewayLLMClient` | `llm/gateway.py` | Zendesk's internal AI gateway |
| `FakeLLMClient` | `tests/` | records prompts, returns a canned answer |

Four different classes, none of which import each other or share a base class — and the service accepts all of them identically. **Switching providers is a one-line config change, not a refactor.** That was the goal of Lesson 06.

### Step 5 — The live adapter: `app/llm/gateway.py`

The adapter is the only file that knows the gateway's URL shape, auth header, and payload format:

```python
async def generate(self, prompt: str) -> str:
    url = f"{self._base_url}/model/{self._model}/invoke"
    headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 16000,
    }
    try:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise LLMTimeoutError("the model did not answer in time") from error
    except httpx.HTTPStatusError as error:
        raise LLMProviderError(f"gateway error: {error.response.status_code}") from error
    ...
    text = next(
        (block["text"] for block in data.get("content", []) if block.get("type") == "text"),
        None,
    )
    if text is None:
        raise LLMResponseValidationError("the model returned no text block")
    return text
```

Explain it in three moves:

1. **Translate out:** our prompt → the gateway's JSON (messages/anthropic_version/max_tokens).
2. **Translate errors:** every possible HTTP failure → one of *our* domain errors, with `from error` preserving the cause chain for debugging. The rest of the app never sees an `httpx` exception.
3. **Translate in:** the gateway's response JSON → plain text, by finding the `text` block (responses are a *list* of typed blocks — never assume position).

`max_tokens=16000` is deliberate: a low cap truncates the reply mid-sentence (we saw this live — a 256-token test cut an answer in half). `timeout=self._timeout` guarantees a hanging gateway fails in 30s instead of hanging the worker forever.

### Step 6 — Who builds what: `app/api/dependencies.py`

```python
def get_chat_service() -> ChatService:
    if settings.llm_provider == "gateway":
        client: LLMClient = GatewayLLMClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    elif settings.llm_provider == "anthropic":
        client = AnthropicLLMClient(...)
    else:
        client = DemoLLMClient()
    return ChatService(llm_client=client)
```

This is the **composition root** — the one place where concrete classes get chosen. Everything else deals in protocols. The branch is driven by `settings.llm_provider`, which comes from `.env` — so "which LLM" is deployment configuration, not code. This is also where tests strike: `client.app.dependency_overrides[get_chat_service] = ...` replaces this whole function with one that injects a fake (Part 7).

### Step 7 — The config flow: `.env` → `Settings` → everywhere

```python
# app/core/config.py
class Settings(BaseSettings):
    llm_provider: str = "demo"
    llm_api_key: str = ""            # secret — never commit, never log
    llm_base_url: str = ""
    llm_model: str = "claude-opus-5"
    llm_timeout_seconds: float = 30.0
    database_url: str = "postgresql+asyncpg://llm:dev@localhost:5432/llm"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

One object, typed, with safe defaults. Precedence: OS environment variables **override** `.env` file values, which override the code defaults. The three-place rule: **safe default in code, real values in untracked `.env`, names-only in committed `.env.example`.**

### Step 8 — When things fail: the error flow

```text
httpx timeout ──► LLMTimeoutError ──────────► 504 {"detail": "The model did not respond in time."}
gateway 5xx ───► LLMProviderError ─────────► 502 {"detail": "The model provider failed."}
bad model JSON ► LLMResponseValidationError ► 502 {"detail": "The model returned an invalid response."}
```

Two different jobs at two different layers:

- The **adapter** raises domain errors (`raise LLMProviderError(...) from error`) — it says *what went wrong* in business language.
- The **handlers** in `app/api/errors.py` (registered once via `register_exception_handlers(app)` from `main.py`) translate them into HTTP status codes — 502/504 mean "a system I depend on failed," which lets callers and monitoring distinguish it from "my code is broken" (500).

Why this matters twice over: the service stays framework-free, and clients never see a raw 500 with a stack trace leaking file paths (we saw the before/after live: first the wall of traceback, then the clean JSON).

### Step 9 — The data layer (built, not yet in the live path)

`db/models.py` defines `Conversation` and `Message` with SQLAlchemy 2.x typed columns; `db/session.py` creates the async engine and session factory from `Settings.database_url`; `repositories/chat.py` is the only file with SQL (it takes a session in its constructor — dependency injection again); `migrations/` holds the Alembic history (one applied migration, async `env.py` because the driver is async).

**Honest current state:** `get_chat_service` does **not** pass a repository into `ChatService` yet — so chats are not saved to Postgres. Every piece exists (models, migration applied, repository, `get_session` dependency); the remaining step is `ChatService(llm_client=client, repository=ChatRepository(session=...))` and a `conversation_id` in the chat flow. That is the first task of the next work session, and a perfect review exercise: you already know every part.

---

## Part 5 — The testing strategy (three levels, three jobs)

| Level | Where | Uses | Proves | Cost |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | fakes for LLM client (and repository) | service logic: prompt building, save order, error propagation | free, milliseconds |
| **API** | `tests/test_*.py` | `TestClient` + `dependency_overrides` | the HTTP chain: routing, validation, injection | free, fast |
| **Smoke** | `scripts/` (+ optional gated test) | the real gateway | the plumbing: token, URL, SDK, network | paid, slow, nondeterministic |

The rules that make this work:

1. **Fakes are plain classes with the right shape** — no mocking library, possible only because of the Protocol (Step 4).
2. **`dependency_overrides` makes API tests provider-proof** — even with `LLM_PROVIDER=gateway` in `.env`, `pytest` never touches the network. One test proves it: the injected service returns `"fake reply"` and the route obeys.
3. **Real calls never run by accident** — smoke runs are explicit (`scripts/smoke_llm.py`, or a test gated behind `LLM_SMOKE=1`). CI must never pay for a push.
4. **A fake test that fails = a logic bug. A smoke test that fails = a wiring bug.** Knowing which one failed tells you where to look before you open a single file.

Run them all:

```bash
poetry run pytest -q                      # levels 1+2: 4 passed
poetry run python scripts/smoke_llm.py    # level 3: one real call
```

---

## Part 6 — Explain it to others (scripts for real conversations)

### The whiteboard version (2 minutes)

Draw the four boxes left to right — **Route → Service → [LLM Client | Repository] → External** — then say:

> "Requests hit FastAPI, which validates with Pydantic and injects a pre-built ChatService. The service runs the workflow: save the user's message, build a prompt, call the LLM, save the reply. The LLM call goes through a protocol — we have three implementations (demo, direct Anthropic, the company gateway) and switching is one env var. Failures inside the adapters become our own exception types, which exception handlers translate into 502/504 so clients never see stack traces. Everything the service depends on is injected, so tests replace the LLM and the database with fakes and run in milliseconds; one gated smoke test checks the real wiring."

### Questions you should now be able to answer

1. **Why is the service FastAPI-free?** → So the workflow is testable and reusable without a web server; the framework is a delivery detail.
2. **Why a Protocol instead of a base class?** → Structural typing: implementations don't import or inherit anything; third-party classes qualify by shape.
3. **Why does the route not just call the SDK?** → Then every test needs the network, provider changes touch every route, and the route owns secrets.
4. **What happens when the gateway is down?** → Adapter raises `LLMProviderError` → handler returns 502 JSON; the user's message was already saved.
5. **Where do prompts live?** → In the service (`_build_prompt`) — they are business logic.
6. **How would you add a second provider?** → One new adapter file satisfying the Protocol, one branch in the composition root, one `.env` line. Nothing else.

### The anti-patterns this design forbids (and why someone might try them)

- *"Just import the SDK in the route, it's faster"* — faster once, then: untestable routes, secrets in HTTP files, and a rewrite for every provider change.
- *"Let the service return HTTP status codes"* — then it can't run outside FastAPI and tests need a server.
- *"Test against the real LLM, it's more realistic"* — nondeterministic, paid, slow; logic bugs need deterministic tests. Real calls prove wiring, not logic.
- *"Hardcode the config"* — a fresh checkout breaks silently; Settings + `.env.example` make setup a copy-paste.

---

## Part 7 — Known gaps (the honest list — each is a next exercise)

- [ ] **Persistence not in the live path** — inject `ChatRepository` in `get_chat_service` and thread `conversation_id` through the chat flow (Lesson 07 Step 7 finish).
- [ ] **`/extract` endpoint not wired** — `schemas/extract.py` exists but has bugs: missing `Field` import, and `str | None` without `from __future__ import annotations` (crashes on import — Lesson 08 Step 6 finish).
- [ ] **Dependency debt** — six packages pip-installed (corporate proxy blocks `poetry add`); pay off on a clean network: `poetry add sqlalchemy alembic asyncpg pydantic-settings httpx anthropic`, then remove `httpx` from the dev group.
- [ ] **No type checking yet** — add mypy (Dashboard item).
- [ ] **Formatting drift** — run `poetry run ruff check . --fix && poetry run ruff format .` (the chat route's indentation is currently non-standard).
- [ ] **Retry loop** — designed (Lesson 08 Step 5) but not yet in the gateway adapter.

## Progress

- Status: **Complete — written 2026-10-05, the day the first real LLM reply came through the full chain**
- Review exercise: explain the whiteboard version aloud, then answer the six questions without notes.

## Review note

This walkthrough is a map of the intended architecture and the code that exists today; it is not a claim that every production checkpoint is finished. Persistence wiring, retry integration, observability, lifespan, Docker, CI, and type checking remain explicitly listed gaps in the dashboard.
