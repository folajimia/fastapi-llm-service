# Lesson 06C — Keep Provider SDK Details Out of Routes

## Objective

Make sure route files know about HTTP, while provider adapters know about provider SDKs.

## The boundary

```text
route.py        → ChatService
ChatService     → LLMClient protocol
provider.py     → provider SDK
```

Only `provider.py` should need to know the provider’s SDK types, authentication setup, request format, and response format.

## What a route should do

The route should eventually:

1. Validate the request body.
2. Obtain a `ChatService` dependency.
3. Call `service.reply(...)`.
4. Translate the result into an HTTP response.

It should not construct prompts, call an SDK, read API keys directly, or decide how provider errors work.

## Example of the separation

```python
# app/llm/provider.py — provider-specific code belongs here
class ProviderLLMClient:
    async def generate(self, prompt: str) -> str:
        # Later: call the selected provider SDK here.
        # This file, not a route, owns that translation.
        raise NotImplementedError
```

```python
# app/api/routes/chat.py — HTTP-specific code belongs here
from fastapi import APIRouter

router = APIRouter()

# The real dependency wiring will be added in the dependency-injection lesson.
```

The second example intentionally does not create a provider client yet. First make the boundary correct; then wire dependencies deliberately. The full worked example — a real adapter for Anthropic's Claude, with error mapping — is [[Lessons/08 Reliable LLM Workflows|Lesson 08]] Step 4.

## Why this matters

- Provider SDK changes affect one adapter instead of every route.
- Service tests do not need FastAPI or a provider.
- Routes stay readable.
- The application can later support a fake, a mock, or a second provider.

## Checkpoint

- [ ] No provider SDK import exists in a route file.
- [ ] No API key is read inside a route function.
- [ ] `ChatService` depends on `LLMClient`, not a provider class.
- [ ] Provider translation is isolated in an adapter module.

## Mentor question

Would this boundary still be useful if the service supported only one provider? Explain your answer in terms of testing, failure handling, and future change—not just “it is cleaner.”

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:
- Commit:

