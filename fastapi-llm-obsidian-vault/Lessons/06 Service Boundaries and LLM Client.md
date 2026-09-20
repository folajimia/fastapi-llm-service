# Lesson 06 — Service Boundaries and the LLM Client

## Objective

Keep HTTP concerns, business logic, persistence, and provider-specific LLM code in separate layers.

## Target architecture

```text
Route → Service → Repository / LLM Client → External system
```

## Responsibilities

- Route: HTTP input/output and status codes.
- Service: business decisions and workflow orchestration.
- Repository: database access.
- LLM client: provider request/response translation.

## Example boundary

```python
from typing import Protocol


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str: ...
```

The service depends on the interface, not on a specific provider SDK. This is useful only if it improves testing or future provider changes; abstractions should earn their complexity.

## Exercise

- [ ] Create a `ChatService` with no FastAPI imports.
- [ ] Create a fake LLM client for tests.
- [ ] Keep provider SDK details out of route files.
- [ ] Test a service response without making a real network call.

## Mentor questions

1. Is the interface useful at this stage, or premature?
2. Which errors should the service raise versus the route translate?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

