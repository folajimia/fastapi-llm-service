# Lesson 09 — Observability and Lifespan

## Objective

Make slow and failed requests diagnosable after the fact — without exposing secrets — and manage shared resources (database pool, LLM client) properly across the application's life.

## The idea in simple terms

When something breaks at 3am, "it didn't work" is useless. You need to answer three questions from your logs alone:

1. **Which request** was it? → request IDs
2. **Where in the chain** did it stall or fail? → one structured log line per stage, all carrying the same request ID
3. **How long** did each stage take? → latency numbers on the log lines

And today, `get_chat_service` builds a fresh `DemoLLMClient` on **every request**. That is like hiring a new employee for each customer. The `lifespan` mechanism fixes it: create shared resources once at startup, close them at shutdown.

## Step 1 — Structured logging with structlog

```bash
poetry add structlog
```

```python
# app/core/logging.py
import logging

import structlog


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
```

Every log line becomes one JSON object you can search, filter, and feed to any log system:

```json
{"event": "chat_reply", "request_id": "a1b2c3", "provider": "demo", "latency_ms": 214, "status": "ok", "timestamp": "2026-09-24T10:15:32Z"}
```

Compare with the alternative — `"Handled chat request a1b2c3 in 214ms ok"` — which no machine can parse. Use `log.info("chat_reply", request_id=..., latency_ms=...)`, **not** f-strings: the fields stay separate and searchable.

## Step 2 — Request ID middleware

One ID per request, generated at the edge, attached to every log line and echoed back to the caller:

```python
# app/api/middleware.py
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()

        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        except Exception:
            log.error("request_failed", path=request.url.path, method=request.method)
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request_finished",
            path=request.url.path,
            method=request.method,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        return response
```

Two things worth understanding:

- `bind_contextvars` stores the request ID in a context variable, so **every log line anywhere in this request** — service, repository, LLM adapter — automatically carries it, with no one passing it around as a parameter.
- The middleware also accepts an incoming `X-Request-ID`. When a frontend sends one, all systems share the same ID; when it does not, we generate one.

Register it in `app/main.py`:

```python
from app.api.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

## Step 3 — Log the LLM call itself

Inside the service (or adapter), one line per LLM call:

```python
log = structlog.get_logger()

async def reply(self, user_message: str) -> str:
    start = time.perf_counter()
    try:
        result = await self._llm_client.generate(prompt)
    except LLMError as error:
        log.error("llm_call_failed", provider="demo", error_type=type(error).__name__)
        raise
    log.info("llm_call", provider="demo", latency_ms=round((time.perf_counter() - start) * 1000, 1))
    return result
```

Allowed fields (safe to log): `event`, `request_id`, `conversation_id`, `provider`, `model`, `latency_ms`, `status`, `token_usage`, `error_type`.

Never logged: API keys, authorization headers, user secrets, sensitive prompt content. `error_type=LLMTimeoutError` yes; `error="key sk-abc123 invalid"` no.

## Step 4 — Health versus readiness

Two different questions, two endpoints:

- `GET /health` — "is the process alive?" Always answers 200 if the app is running. Cheap; never touches the database. Used by the platform to decide *restart*.
- `GET /readiness` — "can I serve traffic right now?" Actually checks dependencies: database reachable, LLM client configured. Used by the load balancer to decide *route traffic here*.

```python
@router.get("/readiness")
async def readiness(session: AsyncSession = Depends(get_session)) -> ReadinessResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return ReadinessResponse(status="ready")
```

If PostgreSQL is down, `/health` still says 200 (the process is fine — restarting it would not fix the database) while `/readiness` says 503 (stop sending traffic).

## Step 5 — Lifespan for shared resources

Replace "build everything per request" with "build once, share, close cleanly":

```python
# app/main.py
from contextlib import asynccontextmanager

from app.db.session import SessionFactory
from app.llm.provider import ProviderLLMClient
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared resources once, before the first request.
    app.state.llm_client = ProviderLLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
    )
    yield
    # Shutdown: after the last request, clean up.
    await app.state.llm_client.aclose()          # e.g. close the httpx client
    await engine.dispose()                        # close the DB connection pool


app = FastAPI(title="LLM Services", version="0.1.0", lifespan=lifespan)
```

Everything before `yield` runs at startup; everything after runs at shutdown. Then the dependency provider stops *constructing* and starts *fetching*:

```python
def get_chat_service(request: Request) -> ChatService:
    client: LLMClient = request.app.state.llm_client
    return ChatService(llm_client=client)
```

FastAPI's `TestClient` triggers lifespan automatically when used as a context manager (as your `conftest.py` already does with `with TestClient(app)`) — which is also how you test startup and shutdown.

## Common mistakes

- **`print()` instead of logging** — invisible in production, unstructured, unfilterable.
- **Logging the prompt or key** — logs are copied, shipped, and retained far more widely than you expect.
- **One health endpoint doing both jobs** — the platform restarts a healthy process (because the DB is down) or keeps routing traffic to a broken one.
- **Creating an `httpx.AsyncClient` per request** — wastes connections; create once in lifespan.
- **Forgetting `engine.dispose()`** — shutdown hangs or complains about open connections.

## Checkpoint

- [ ] `structlog` configured; log lines are single JSON objects.
- [ ] Request ID middleware generates/propagates IDs and returns `X-Request-ID`.
- [ ] LLM calls log success and failure with `latency_ms` and `error_type`.
- [ ] `/health` and `/readiness` exist with distinct meanings; readiness returns 503 when the database is unavailable.
- [ ] Shared resources (LLM client, engine) are created in `lifespan` and closed on shutdown; dependencies fetch from `app.state`.
- [ ] No secrets or prompt content appear in any log line.

## Mentor questions

1. Which fields are safe to log for this service? Would you log `message` lengths but not contents?
2. What should `/readiness` do if PostgreSQL is unavailable — and what should the *platform* do with that answer?
3. How will tests exercise startup and shutdown? (Hint: `with TestClient(app)` — why does that work?)

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

## References

[FastAPI — Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) · [structlog — documentation](https://www.structlog.org/en/stable/) · [Starlette — Middleware](https://www.starlette.io/middleware/)
