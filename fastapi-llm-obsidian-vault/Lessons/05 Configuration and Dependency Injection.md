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

**Safety rule:** source-code defaults must be safe to share. Use an empty string or a local demo value for an API key, never a real token. Put real values in an untracked `.env` file and keep only variable names in `.env.example`.

## Target structure

```text
app/
├── core/config.py          # Settings (typed configuration)
├── api/dependencies.py     # dependency providers like get_chat_service
└── api/routes/             # routes that receive dependencies via Depends
```

## Example

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Service"
    environment: str = "development"
    llm_api_key: str
    llm_model: str = "some-model"
    llm_timeout_seconds: float = 30.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

Do not commit `.env`. Commit a safe `.env.example` containing names but no secrets.

## Exercise

- [x] Add typed settings.
- [x] Add `.env` to `.gitignore`.
- [x] Add `.env.example`.
- [x] Inject a settings object into one route or service.
- [ ] Override the dependency in a test.

## Mentor questions

1. Should settings be cached as one application-level object?
2. Which settings are required in production but optional locally?

## Progress

- Status: **Complete**
- Completed: [x] typed settings [x] `.env` gitignored [x] `.env.example` [x] settings + service injected into routes [x] dependency override in an API test
- Date:
