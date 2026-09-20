# Lesson 01 — Project Setup with Poetry

## Objective

Create a reproducible Python project whose dependencies can be installed consistently by you, your mentor, CI, and Docker.

## Concepts

- Virtual environment
- Poetry
- `pyproject.toml`
- `poetry.lock`
- Production versus development dependencies

## Why this matters

A virtual environment prevents projects from sharing accidental packages. Poetry records what the project needs; the lockfile records the exact versions resolved for the project. This reduces “it works on my machine” problems.

## What we will build

```text
fastapi-llm-service/
├── app/
├── tests/
├── docs/
├── pyproject.toml
├── poetry.lock
└── README.md
```

## Commands

```bash
poetry new --src fastapi-llm-service
cd fastapi-llm-service
poetry add fastapi uvicorn
poetry add --group dev pytest ruff
poetry lock
poetry install
poetry run python --version
poetry run pytest
```

If the existing project already exists, do not recreate it. Run `poetry init`, answer the prompts, then use `poetry add` and commit both `pyproject.toml` and `poetry.lock`.

## Important correction

The earlier `venv + pip` instructions are valid for learning Python, but they are not the final dependency workflow for this project because the mentorship requirement is Poetry plus a committed lockfile. Keep the existing `.venv` temporarily if useful, then use Poetry as the authoritative workflow.

## Exercise

- [x] Install Poetry.
- [x] Create or update `pyproject.toml`.
- [x] Add runtime and development dependency groups.
- [x] Generate and commit `poetry.lock`.
- [x] Run the project through `poetry run`.

## Mentor questions

1. Should this project use a `src/` layout or keep `app/` at the root?
2. Which packages belong in runtime dependencies, and which belong in the dev group?
3. What Python version should the service support?

## Progress

- Status: **Started**
- Completed: [ ]
- Evidence/commit:
- Time spent:

## Reference

[Poetry basic usage](https://python-poetry.org/docs/basic-usage/)

