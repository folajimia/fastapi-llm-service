# FastAPI LLM Service — Learning Dashboard

> Main goal: **Build a clean, maintainable FastAPI service that supports LLM app workflows and production-ready patterns.**

## How to use this vault

1. Work through lessons in order.
2. Tick a checkbox only after you can run the command or explain the idea.
3. Put uncertain points in [[Questions for Mentor]].
4. After each Friday check-in, create a note in `Mentor Meetings`.
5. Record important design choices in `Architecture Decisions`.

## Current status

- Course status: **Lessons 01–06 are working; Lessons 07–08 are partially implemented; Lessons 09–10 remain planned**
- Current next action: finish the persistence wiring and its tests, then continue with [[Lessons/09 Observability and Lifespan|Lesson 09]]
- Read [[Lessons/11 Architecture Walkthrough|Lesson 11 — Architecture Walkthrough]] to review the whole system and practice explaining it
- Open debts: production dependencies are not fully declared in `pyproject.toml`; update `pyproject.toml` and `poetry.lock` together before relying on a clean checkout or Docker build.
- Project constraint: use **Poetry**, commit `poetry.lock`, separate production/development dependencies, and build Docker with Poetry.

## Progress

- [x] Understand the service goal and 10-week roadmap
- [x] Migrate the project setup to Poetry and commit `poetry.lock`
- [x] Create a minimal FastAPI application
- [x] Create `/api/v1/health`
- [x] Separate routes with `APIRouter`
- [x] Run and verify the health test locally
- [x] Add Ruff configuration (formatting pass still pending)
- [ ] Add type-checking (mypy) to the project workflow
- [x] Add typed configuration and dependency injection (provider override is tested)
- [x] Add service and LLM-client boundaries (Protocol + adapters + composition root)
- [ ] Add PostgreSQL, SQLAlchemy, and Alembic (models and migration exist; live repository wiring and integration test remain)
- [x] Add deterministic chat tests (fakes + dependency override)
- [ ] Add reliable LLM workflows (errors and timeout adapters exist; retry integration and structured-output endpoint remain)
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
| [[Lessons/05 Configuration and Dependency Injection|05]] | Settings and dependencies | Complete |
| [[Lessons/06 Service Boundaries and LLM Client|06]] | Application architecture | Complete (06A–06D) |
| [[Lessons/07 Persistence and Migrations|07]] | PostgreSQL, SQLAlchemy, Alembic | In progress — repository wiring remains |
| [[Lessons/08 Reliable LLM Workflows|08]] | Errors, timeouts, retries, structured output, real provider | In progress |
| [[Lessons/09 Observability and Lifespan|09]] | Logs, IDs, health, readiness, resources | Not started |
| [[Lessons/10 Docker CI and Final Review|10]] | Docker, CI, production-oriented completion | Not started |
| [[Lessons/11 Architecture Walkthrough|11]] | The whole system explained — read, understand, teach | **New — read this next** |
| [[Lessons/12 Memory and Personalization|12]] | Conversation history + user facts: making the LLM remember | Complete — verified live (2026-11-10) |

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

## Review result

The architecture, beginner-explanation, and technical-quality reviews agree on the same boundary: routes handle HTTP, services coordinate workflows, adapters talk to external providers, repositories talk to the database, and tests replace external systems with fakes. The remaining unchecked items are implementation work, not missing architectural chapters.

Review findings reflected in the lessons and code:

- Secrets have safe defaults in source code; real values belong only in untracked `.env` files.
- `ChatService` is wired to the route and tested through a dependency override.
- Persistence models and migrations exist, but the repository is not yet injected into live chat requests.
- The retry helper is taught, but retry behavior is not yet integrated into the provider adapter.
- The structured-output schema is importable, but the `/extract` workflow and endpoint still need to be built.
- Observability, lifespan, Docker, CI, and type checking remain future work.

## Weekly rhythm

Before Friday: implementation, tests, decisions, questions. During Friday: review boundaries, trade-offs, failures, and next homework. After Friday: update the dashboard and create a mentor note.
