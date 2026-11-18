# Lesson 06A — Create `ChatService` Without FastAPI

## Objective

Create the application service that owns chat behavior while importing **nothing from FastAPI**.

## The idea in simple terms

The route is the front desk. It receives an HTTP request and returns an HTTP response. The service is the worker behind the desk. It should be able to do its job even if FastAPI is replaced by a command-line tool, a background job, or another web framework.

## Target flow

```text
HTTP route → ChatService → LLMClient → provider SDK/API
```

## Step 1 — Create the folders

```text
app/
├── api/routes/
├── llm/
│   └── client.py
└── services/
    └── chat.py
```

Create missing package files if your project needs them:

```bash
mkdir -p app/llm app/services
touch app/llm/__init__.py app/services/__init__.py
```

## Step 2 — Define the LLM boundary

```python
# app/llm/client.py
from typing import Protocol


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
```

`Protocol` describes the behavior a client must provide. It does not choose OpenAI, Anthropic, or another provider.

## Step 3 — Create the service

```python
# app/services/chat.py
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
```

Notice what is absent: no `FastAPI`, `APIRouter`, `Request`, `HTTPException`, or provider SDK import.

**Careful with the `\n` above.** In Python source code, `"\n"` (one backslash) is a newline character. `"\\n"` (two backslashes) is a literal backslash followed by the letter `n` — the prompt would contain the *characters* `\n` instead of a line break. If your test asserts `\\n` and passes, the test has learned the bug, not verified the behavior.

## Why the constructor receives the client

This is dependency injection in plain Python. The service does not create its own client. The caller supplies one. That lets production code supply a real client and tests supply a fake one.

## Common mistakes

- **Writing `\\n` instead of `\n`** in the prompt — see the warning above. A double backslash puts a literal `\n` into the text instead of a line break.
- **Importing FastAPI "just for types"** — the moment `chat.py` imports anything from `fastapi`, the service can no longer run without a web framework. Keep it pure Python.
- **Constructing the LLM client inside the service** — `ChatService(DemoLLMClient())` inside `reply()` would hardcode the dependency and make fakes impossible.

## Checkpoint

- [ ] `chat.py` has no FastAPI imports.
- [ ] `ChatService` receives an `LLMClient` in its constructor.
- [ ] Prompt construction is inside the service, not the route.
- [ ] The service returns the LLM result.

## Explain it to your mentor

> I kept `ChatService` independent of FastAPI so the business workflow can be tested and reused without starting an HTTP server. The LLM client is injected because the service should not construct provider-specific dependencies itself.

## Progress

- Status: **In progress — code exists and the unit test passes; fix the `\\n` escape bug in `app/services/chat.py` and the matching assertion in `tests/unit/test_chat_service.py` (see [[Lessons/06B Wiring the Route to the Service|06B]] Step 3), then mark complete.**
- Completed: [x] `chat.py` has no FastAPI imports. [x] `ChatService` receives an `LLMClient` in its constructor. [x] Prompt construction is inside the service. [ ] The prompt uses a real newline (`\n`, not `\\n`).
- Date:
- Commit:

## Review note

The prompt now uses a real newline (`\n`), and the unit test checks that same value. The earlier double-escape warning is retained above as a teaching example of how the bug looked.
