# Lesson 06 — Service Boundaries and the LLM Client

## Objective

Keep HTTP concerns, business logic, persistence, and provider-specific LLM code in separate layers, and wire them together with dependency injection.

This lesson is split into four parts, done in order:

| Part | Topic | Status |
|---|---|---|
| [[Lessons/06A ChatService Without FastAPI\|06A]] | Create `ChatService` with no FastAPI imports | Complete |
| [[Lessons/06B Wiring the Route to the Service\|06B]] | Wire the route to the service with `Depends` | Complete |
| [[Lessons/06C Provider Isolation\|06C]] | Keep provider SDK details out of routes | Complete conceptually; adapter tests remain |
| [[Lessons/06D Testing the ChatService\|06D]] | Test the service with a fake LLM client | Complete for the basic workflow |

## Target architecture

```text
Route → Service → Repository / LLM Client → External system
```

The repository layer arrives in [[Lessons/07 Persistence and Migrations|Lesson 07]]; this lesson builds the route → service → LLM client chain.

## Responsibilities

- Route: HTTP input/output, status codes, dependency injection. Nothing else.
- Service: business decisions and workflow orchestration (prompt building is a service job).
- Repository: database access (Lesson 07).
- LLM client: provider request/response translation (Lesson 08).

## Example boundary

```python
from typing import Protocol


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str: ...
```

The service depends on the interface, not on a specific provider SDK. This is useful only if it improves testing or future provider changes; abstractions should earn their complexity.

## Where the project stands right now

Already built: `ChatService` ([[Lessons/06A ChatService Without FastAPI|06A]]), the `LLMClient` protocol, `DemoLLMClient` in `app/api/dependencies.py`, and a passing unit test ([[Lessons/06D Testing the ChatService|06D]]).

The basic route → service → fake-client chain is now complete. The next architecture exercise is in Lesson 07: inject the repository into the same service without moving database code into the route.

## Exercise

- [x] Create a `ChatService` with no FastAPI imports (06A).
- [x] Wire the route to the service with `Depends` (06B).
- [x] Add a dependency-override test proving the route accepts an injected fake (06B Step 5).
- [x] Keep provider SDK details out of route files (06C).
- [x] Test a service response and a provider failure without a real network call (06D).

## Mentor questions

1. Is the interface useful at this stage, or premature?
2. Which errors should the service raise versus the route translate? (Answered in [[Lessons/08 Reliable LLM Workflows|Lesson 08]].)

## Progress

- Status: **Complete for the basic service boundary; persistence and production reliability continue in Lessons 07–09**
- Completed: [x] Service without FastAPI [x] LLM client protocol [x] Fake client in unit tests [x] Route wired to service [x] Prompt uses a real newline
- Date:
- Commit:
