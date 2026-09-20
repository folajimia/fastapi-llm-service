# Lesson 02 — A Minimal FastAPI Application

## Objective

Create the smallest working FastAPI application and understand what the application object does.

## Concepts

- ASGI application
- Uvicorn
- OpenAPI
- Interactive API documentation

## Why this matters

FastAPI defines the web application. Uvicorn runs it. Keeping this distinction clear makes local development and later deployment easier to reason about.

## Code

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(
    title="LLM Service",
    version="0.1.0",
)
```

## Commands

```bash
poetry run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

`app.main:app` means: import the `app` package, open `main.py`, and use the variable named `app`.

## Exercise

- [x] Start the server.
- [x] Open Swagger UI at `/docs`.
- [x] Confirm the title and version are visible.
- [x] Stop the server with `Ctrl+C`.

## Common mistakes

- Running the command outside the project root.
- Using `python` from the wrong environment.
- Naming the application variable something different without changing the Uvicorn command.

## Mentor questions

1. What should belong in `main.py`, and what should not?
The file i created has the router import and inclusion commented out. That means my routes are not registered, so `/api/v1/health` will return `404`.

Things that belong in `main.py`:

- Create the `FastAPI` application
- Set application metadata such as title and version
- Include API routers
- Configure middleware
- Register global exception handlers
- Configure startup/shutdown or lifespan behavior
- Optionally expose health/readiness infrastructure

Things that generally should not belong there:

- Endpoint implementation logic
- LLM client code
- Database queries
- Request/response schemas
- Business rules
- Large configuration definitions
- Test code
- Secrets or API keys

## Progress

- Status: **Complete conceptually**
- Verified locally: [ ]
- Date:

