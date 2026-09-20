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

- [x] Create `tests/test_health.py`.
- [x] Run the test.
- [x] Deliberately change the expected status to see the test fail.
- [x] Restore the correct expectation.
- [x] Add a `pyproject.toml` Ruff configuration.

## Common mistakes

- Testing `/health` instead of `/api/v1/health`.
- Running tests from a directory where imports cannot find `app`.
- Treating a passing test as proof that all production behavior is correct; it only proves this one behavior.

## Mentor questions

1. Should `TestClient` be created once or through a fixture in this project?
For this project, use a pytest fixture. It keeps tests isolated and makes it easier to add authentication, dependency overrides, or database setup later.
2. Which tests belong at unit, API, and database-integration level?

#### Unit tests

Test one piece of Python logic in isolation, without making HTTP requests or using a real database.

Examples:

- Message formatting
- Input transformation
- Token/cost calculations
- LLM service retry logic
- Validation helpers
- Business rules

Example:

```
def test_format_reply():
    assert format_reply("hello") == "You said: hello"
```

Mock external services such as LLM APIs, databases, and HTTP clients.

#### API tests

Test the FastAPI application through HTTP using `TestClient`.

Your current test is an API-level test because it calls:

```
client.get("/api/v1/health")
```

Typical API tests cover:

- HTTP status codes
- Request validation
- Response JSON
- Authentication behavior
- Routing
- Error responses
- Headers

Examples:

```
def test_health_check(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

For the chat endpoint, you might test valid input, missing fields, and response structure.

#### Database integration tests

Test your application against a real database or a test database.

Examples:

- Creating and retrieving records
- Database constraints
- Queries and relationships
- Transactions and rollbacks
- Migrations
- Repository code

These tests are slower and should usually be separated from fast unit/API tests. Avoid using your production database; use a temporary test database or isolated schema.

A typical structure would be:

```
tests/
├── conftest.py
├── unit/
│   ├── test_services.py
│   └── test_helpers.py
├── api/
│   ├── test_health.py
│   └── test_chat.py
└── integration/
    ├── test_database.py
    └── test_repositories.py
```

For the current project, you need API tests now. 


Notes
ruff is a Python development tool that checks and formats your code.

It can:

- Find unused imports and undefined variables
- Enforce style rules
- Sort imports
- Detect common bugs
- Format Python files automatically
## Progress

- Status: **Next**
- Completed: [ ]
- Test output/commit:
- Date:

## Reference

[FastAPI — Testing](https://fastapi.tiangolo.com/tutorial/testing/)

