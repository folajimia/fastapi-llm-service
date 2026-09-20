# Lesson 04 — Testing the Health Endpoint

## Objective

Write and run an automated API test before adding application complexity.

## Concepts

- Test client
- Assertion
- Regression test
- Test isolation

## Why this matters

The test becomes a small safety net. If routing, configuration, or startup changes later break the health endpoint, the test should show it immediately.

## Code

```python
# tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

## Commands

```bash
poetry run pytest
poetry run ruff check .
```

## Exercise

- [ ] Create `tests/test_health.py`.
- [ ] Run the test.
- [ ] Deliberately change the expected status to see the test fail.
- [ ] Restore the correct expectation.
- [ ] Add a `pyproject.toml` Ruff configuration.

## Common mistakes

- Testing `/health` instead of `/api/v1/health`.
- Running tests from a directory where imports cannot find `app`.
- Treating a passing test as proof that all production behavior is correct; it only proves this one behavior.

## Mentor questions

1. Should `TestClient` be created once or through a fixture in this project?
2. Which tests belong at unit, API, and database-integration level?

## Progress

- Status: **Next**
- Completed: [ ]
- Test output/commit:
- Date:

## Reference

[FastAPI — Testing](https://fastapi.tiangolo.com/tutorial/testing/)

