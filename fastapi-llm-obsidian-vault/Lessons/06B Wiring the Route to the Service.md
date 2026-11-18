# Lesson 06B — Wire the Route to the Service

## Objective

Connect `POST /api/v1/chat` to `ChatService` using FastAPI dependency injection, so the route delegates to the service instead of doing the work itself.

This is the lesson that connects [[Lessons/06A ChatService Without FastAPI|06A]] (the service) to [[Lessons/06C Provider Isolation|06C]] (provider boundaries). Until it is done, the service exists but nothing calls it.

## The idea in simple terms

The route is the front desk. The service is the worker behind the desk. The **dependency function** is the staffing department: it builds a ready-to-use `ChatService` (with its LLM client) and hands it to the route on every request.

Why not just create the service inside the route? Three reasons:

1. The route file would need to import the LLM client — breaking the boundary from 06C.
2. Tests could not swap in a fake without editing the route.
3. Every route that needs chat would repeat the same construction code.

## Current state (what is broken right now)

`app/api/routes/chat.py` currently looks like this:

```python
@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest,
service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return ChatResponse(reply=f"You said: {request.message}")
    return ChatResponse(reply=reply)
```

Read it carefully — there are two bugs:

**Bug 1: the first return echoes the message and ignores the service.** The endpoint receives a `ChatService` (line 2) and never uses it. It just parrots `"You said: ..."` back. The test passes because the test asserts the echo — a test that passes for the wrong reason.

**Bug 2: the second return is dead code.** Python stops executing a function at the first `return`. Anything after it never runs. And even if it could run, `reply` was never defined, so it would crash with `NameError: name 'reply' is not defined`. This is an unfinished edit: the wiring was started and abandoned halfway.

## Step 1 — Check the dependency provider

This file should already exist from [[Lessons/05 Configuration and Dependency Injection|Lesson 05]]:

```python
# app/api/dependencies.py
from app.llm.client import LLMClient
from app.services.chat import ChatService


class DemoLLMClient:
    async def generate(self, prompt: str) -> str:
        return f"Demo response for: {prompt}"


def get_chat_service() -> ChatService:
    client: LLMClient = DemoLLMClient()
    return ChatService(llm_client=client)
```

Two things to understand:

- `DemoLLMClient` is a **temporary stand-in**. In [[Lessons/08 Reliable LLM Workflows|Lesson 08]] it is replaced by the real provider client from `app/llm/provider.py`, built from `Settings`.
- The `client: LLMClient = ...` annotation is documentation: it says "this function promises to return something matching the `LLMClient` protocol." `DemoLLMClient` satisfies the protocol structurally — it has an async `generate` method — without inheriting from anything.

## Step 2 — Fix the route

```python
# app/api/routes/chat.py
from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    reply = await service.reply(request.message)
    return ChatResponse(reply=reply)
```

What changed and why:

- **Deleted both old returns.** No echo, no dead code.
- **`reply = await service.reply(...)`** — `service.reply()` is an `async` function, so it returns a *coroutine*, not a string. `await` waits for the actual result. Forgetting `await` is the most common async mistake; you would get a confusing serialization error instead of a reply.
- The route now does exactly four things: validate input (FastAPI does this via `ChatRequest`), get the service, call it, wrap the result in `ChatResponse`. That is the whole job of a route.

## Step 3 — Fix the escaped newline in the prompt

While you are in the area, check `app/services/chat.py`. It currently contains:

```python
return f"You are a helpful assistant.\\nUser: {user_message}"
```

In Python source code, `\\n` means "a literal backslash, then the letter n". The prompt sent to the LLM contains the **characters** `\n`, not a line break. You want `"\n"` — a single backslash. Fix the service **and** the assertion in `tests/unit/test_chat_service.py`, which currently expects the wrong string and therefore passes while asserting the bug.

See [[Lessons/06A ChatService Without FastAPI|06A]] → Common mistakes for the full explanation.

## Step 4 — Update the API test

```python
# tests/test_chat.py
test_chat

This test now proves the full chain: route → dependency provider → service → demo client → response.

## Step 5 — Prove the route is decoupled from the demo client

The strongest version of this test overrides the dependency, so the route is tested with a **fake service** and never touches `DemoLLMClient`:

```python
# tests/test_chat.py
from fastapi.testclient import TestClient

from app.api.dependencies import get_chat_service
from app.services.chat import ChatService


class FakeLLMClient:
    async def generate(self, prompt: str) -> str:
        return "fake reply"


def test_chat_route_uses_injected_service(client):
    client.app.dependency_overrides[get_chat_service] = lambda: ChatService(
        llm_client=FakeLLMClient()
    )
    try:
        response = client.post("/api/v1/chat", json={"message": "Hello"})
        assert response.json() == {"reply": "fake reply"}
    finally:
        client.app.dependency_overrides.clear()
```

How `dependency_overrides` works: FastAPI sees `Depends(get_chat_service)` in the route, checks the overrides table first, and if `get_chat_service` is in it, calls the override instead. The route never knows. This is the same trick you will use to swap the real database for a fake in [[Lessons/07 Persistence and Migrations|Lesson 07]].

This also completes the last unchecked exercise from Lesson 05: "Override the dependency in a test."

## Step 6 — Verify by hand

```bash
poetry run pytest -q                # all tests pass
poetry run uvicorn app.main:app --reload
curl -X POST localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello"}'
```

Expected response:

```json
{"reply": "Demo response for: You are a helpful assistant.\nUser: Hello"}
```

If you still see `"You said: Hello"`, the route fix is not actually saved or the server needs a restart.

## Common mistakes

- **Forgetting `await`** on an async call — you get a coroutine object, not the result.
- **Building the service inside the route** — defeats dependency injection; tests can no longer substitute fakes.
- **Leaving unreachable code after a `return`** — dead code hides unfinished work and confuses the next reader (including future you).
- **A test that asserts the echo** — it passes while proving nothing. Always ask: is this test passing because the behavior is right, or because it learned the code's bad habit?

## Checkpoint

- [ ] The route calls `await service.reply(...)` and uses its result.
- [ ] No dead code or echo remains in `chat.py`.
- [ ] The prompt contains a real newline (single `\n`), and the unit test asserts it.
- [ ] The API test expects the demo client's response.
- [ ] A dependency-override test proves the route works with an injected fake.
- [ ] `poetry run pytest` passes and a manual `curl` returns the demo reply.

## Explain it to your mentor

> The route delegates to `ChatService` through `Depends(get_chat_service)`, so HTTP code never constructs business dependencies. Tests override the dependency provider with a fake, which proves the route is coupled only to the service's interface, not to a specific LLM client or provider.

## Mentor questions

1. Should `get_chat_service` build a new service per request, or should one instance be shared? (We revisit this in Lesson 09 with `lifespan`.)
2. What is the right HTTP status code when the LLM client fails? (Preview of Lesson 08.)

## Progress

- Status: **Complete**
- Completed: [x] route delegates to service [x] prompt newline fixed [x] dependency override test
- Date:
- Commit:

## Review note

The route is now wired to `ChatService`, has no echo/dead-code path, and is covered by the dependency-override API test. The “currently broken” section above is preserved as a before-and-after teaching example.
