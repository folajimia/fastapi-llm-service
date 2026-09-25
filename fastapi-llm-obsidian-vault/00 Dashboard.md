# FastAPI LLM Service — Learning Dashboard

> Main goal: **Build a clean, maintainable FastAPI service that supports LLM app workflows and production-ready patterns.**

## How to use this vault

1. Work through lessons in order.
2. Tick a checkbox only after you can run the command or explain the idea.
3. Put uncertain points in [[Questions for Mentor]].
4. After each Friday check-in, create a note in `Mentor Meetings`.
5. Record important design choices in `Architecture Decisions`.

## Current status

- Course status: **In progress — Lessons 01–05 done, Lesson 06 ~80% built**
- Current next action: Complete [[Lessons/06B Wiring the Route to the Service|Lesson 06B — Wiring the Route to the Service]] (the missing sub-lesson that fixes the half-finished chat route)
- Open bugs to fix as part of 06B: the chat route ignores the service (echo + dead code), and the prompt has a `\\n` double-escape in both the service and its test.
- Project constraint: use **Poetry**, commit `poetry.lock`, separate production/development dependencies, and build Docker with Poetry.

## Progress

- [x] Understand the service goal and 10-week roadmap
- [x] Migrate the project setup to Poetry and commit `poetry.lock`
- [x] Create a minimal FastAPI application
- [x] Create `/api/v1/health`
- [x] Separate routes with `APIRouter`
- [x] Run and verify the health test locally (3 tests pass)
- [x] Add Ruff configuration (run `ruff check . --fix` + `ruff format .` until clean)
- [ ] Add type-checking (mypy) to the project workflow
- [x] Add typed configuration and dependency injection (one test override remains, done in 06B)
- [ ] Add service and LLM-client boundaries (in progress — 06B is the missing piece)
- [ ] Add PostgreSQL, SQLAlchemy, and Alembic
- [ ] Add deterministic LLM workflow tests
- [ ] Add errors, timeouts, retries, and structured outputs
- [ ] Add request IDs, structured logging, health/readiness, and lifespan
- [ ] Add Docker and CI
- [ ] Complete final architecture review

## Lesson map

| Lesson | Topic | Status |
|---|---|---|
| [[Lessons/01 Project Setup with Poetry|01]] | Project setup and reproducibility | Complete |
| [[Lessons/02 FastAPI Application|02]] | Minimal FastAPI application | Complete |
| [[Lessons/03 Routing and API Versioning|03]] | Routers and `/api/v1` | Complete |
| [[Lessons/04 Testing the Health Endpoint|04]] | API testing | Complete |
| [[Lessons/05 Configuration and Dependency Injection|05]] | Settings and dependencies | Mostly complete |
| [[Lessons/06 Service Boundaries and LLM Client|06]] | Application architecture | In progress — 06B next |
| [[Lessons/07 Persistence and Migrations|07]] | PostgreSQL, SQLAlchemy, Alembic | Not started |
| [[Lessons/08 Reliable LLM Workflows|08]] | Errors, timeouts, retries, structured output | Not started |
| [[Lessons/09 Observability and Lifespan|09]] | Logs, IDs, health, readiness, resources | Not started |
| [[Lessons/10 Docker CI and Final Review|10]] | Docker, CI, production-oriented completion | Not started |

## Definition of done

- [ ] Clean module boundaries documented in `Architecture Decisions`.
- [ ] Typed settings and secrets outside source control.
- [ ] Request/response validation.
- [ ] Provider-independent LLM integration where useful.
- [ ] Explicit timeout, error, and retry behavior.
- [ ] PostgreSQL persistence with versioned migrations.
- [ ] Unit, API, and integration tests with a fake LLM client.
- [ ] Structured logs and request correlation.
- [ ] Health and readiness endpoints.
- [ ] Dockerized execution and automated CI.
- [ ] API documentation and graceful startup/shutdown.

## Weekly rhythm

Before Friday: implementation, tests, decisions, questions. During Friday: review boundaries, trade-offs, failures, and next homework. After Friday: update the dashboard and create a mentor note.

