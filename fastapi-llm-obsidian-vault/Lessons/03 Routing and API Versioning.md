# Lesson 03 — Routing and API Versioning

## Objective

Organize endpoints into route modules and expose them under a versioned API prefix.

## Concepts

- `APIRouter`
- Path operation
- HTTP method
- API versioning
- Separation of responsibilities

## Why this matters

`main.py` should assemble the application, not contain every endpoint. Route modules make the code easier to find and allow future changes such as `/api/v2` without rewriting the whole service.

## Code

```python
# app/api/routes/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# app/api/router.py
from fastapi import APIRouter

from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="LLM Service", version="0.1.0")
app.include_router(api_router, prefix="/api/v1")
```

## Request flow

```text
Client → main.py → api/router.py → health.py → HTTP response
```

## Exercise

- [x] Confirm `GET /api/v1/health` appears in `/docs`.
- [x] Call it with `curl`.
- [x] Add a temporary `/ping` route and remove it after testing.

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Progress

- Status: **Complete conceptually**
- Verified locally: [ ]
- Date:

## Reference

[FastAPI — Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

