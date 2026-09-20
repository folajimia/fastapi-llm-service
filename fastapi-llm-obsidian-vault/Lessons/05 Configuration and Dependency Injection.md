# Lesson 05 — Configuration and Dependency Injection

## Objective

Load typed settings from environment variables and use FastAPI dependencies to provide shared application components without hiding their creation.

## Concepts

- Environment variable
- Secret
- Pydantic Settings
- Dependency injection
- `Depends`

## Why this matters

Secrets must not live in source code. Dependency injection makes a route’s requirements visible and makes tests easier because dependencies can be replaced with fakes.

## Target structure

```text
app/
├── core/config.py
├── dependencies.py
└── api/routes/
```

## Example

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Service"
    environment: str = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

Do not commit `.env`. Commit a safe `.env.example` containing names but no secrets.

## Exercise

- [ ] Add typed settings.
- [ ] Add `.env` to `.gitignore`.
- [ ] Add `.env.example`.
- [ ] Inject a settings object into one route or service.
- [ ] Override the dependency in a test.

## Mentor questions

1. Should settings be cached as one application-level object?
2. Which settings are required in production but optional locally?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

