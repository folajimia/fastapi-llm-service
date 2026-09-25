# Lesson 10 — Docker, CI, and Final Review

## Objective

Make the service reproducible for another developer (and a server) and prevent broken changes from reaching the main branch.

## The idea in simple terms

"Works on my machine" is not done. Done means: a clean checkout on a fresh machine runs with the documented commands. Two tools enforce that:

- **Docker** packages the app plus its exact Python environment into an image that behaves identically everywhere.
- **CI** (GitHub Actions) re-runs your checks on every push and pull request, so a broken change is caught before merge — including changes you forgot to test locally.

## Step 1 — The Dockerfile

Two rules for a good Python image: install dependencies in a layer that rarely changes (copy only the lockfiles first), and do not run as root.

```dockerfile
# Dockerfile
FROM python:3.12-slim

ENV POETRY_VERSION=2.0.0 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

# Install Poetry; --only main skips dev tools (pytest, ruff) — smaller image
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copy only dependency files first: this layer is cached until they change
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# Now the code — changes here do not reinstall dependencies
COPY app ./app

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Why the two-step copy: Docker builds in layers. If `pyproject.toml`/`poetry.lock` are unchanged but `app/` changed, the expensive dependency-install layer is reused and the build takes seconds instead of minutes.

Also add a `.dockerignore`:

```text
.venv
.git
__pycache__
.pytest_cache
.env
fastapi-llm-obsidian-vault
```

The `.env` line matters: without it, your secrets get baked into the image.

Verify it builds and runs:

```bash
docker build -t llm-service .
docker run --rm -p 8000:8000 llm-service
curl localhost:8000/api/v1/health
```

## Step 2 — Docker Compose: app + PostgreSQL together

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://llm:dev@db:5432/llm
      LLM_API_KEY: ${LLM_API_KEY}     # read from your local .env, not committed
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: llm
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: llm
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U llm"]
      interval: 5s
      retries: 5
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Note the hostname in `DATABASE_URL` is `db`, not `localhost` — inside the Compose network, containers reach each other by service name. `condition: service_healthy` makes the API wait until Postgres actually accepts connections, not merely until its container started.

```bash
docker compose up --build      # whole stack: API + database
docker compose exec api poetry run alembic upgrade head   # apply migrations
```

## Step 3 — The clean-checkout test

The definition of done for this step: from a fresh clone,

```bash
git clone <repo-url> fresh-copy && cd fresh-copy
poetry install
cp .env.example .env          # fill in the local values
poetry run pytest -q
docker compose up --build
curl -X POST localhost:8000/api/v1/chat -H 'Content-Type: application/json' -d '{"message":"hi"}'
```

…all of it works, using only the README. If any step needs undocumented tribal knowledge, write that knowledge into the README now, while you still remember it.

## Step 4 — GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Poetry
        run: pipx install poetry

      - name: Install dependencies
        run: poetry install --with dev

      - name: Lint
        run: |
          poetry run ruff check .
          poetry run ruff format --check .

      - name: Type check
        run: poetry run mypy app

      - name: Tests
        run: poetry run pytest -q
```

The pipeline is literally the commands you already run locally — that is the point. If CI fails, you should be able to reproduce the failure on your machine with the same command. (Type checking assumes mypy was added in the earlier lesson; if it was not, add it or remove that step.)

A Docker-build step (`docker build .`) can be added once the basics are green.

## Step 5 — README as the front door

The README should answer, in order: What is this? How do I run it? How do I test it? Where do secrets go?

```markdown
## Setup
poetry install
cp .env.example .env   # then fill in values

## Run
docker compose up --build
# or locally: poetry run uvicorn app.main:app --reload

## Test
poetry run pytest -q
poetry run ruff check .
```

## Final architecture review

Walk the list honestly — this is the course's Definition of Done:

- [ ] Routes do not contain database queries or provider SDK calls.
- [ ] Services do not depend on FastAPI request objects unnecessarily.
- [ ] Provider-specific code is isolated in one adapter module.
- [ ] Configuration is typed and secret-safe (no secrets in git or images).
- [ ] Migrations are committed and reviewed.
- [ ] Tests include a fake LLM and cover timeout, retry, and invalid output.
- [ ] Logs can explain a slow request end-to-end via request IDs.
- [ ] Docker and CI work from a clean checkout.

## Common mistakes

- **`COPY . .` in the Dockerfile** — copies `.env` and `.venv` into the image; slow and leaky. Use `.dockerignore` and copy only what runs.
- **Running as root in the container** — a compromised process gets root permissions for free.
- **`docker compose up` without `service_healthy`** — the API starts before Postgres accepts connections and crashes on boot.
- **CI without the same commands you run locally** — the moment they drift, CI failures become unexplainable.
- **Documenting setup "later"** — later you will have forgotten the one flag that mattered.

## Mentor questions

1. What would you simplify before calling this production-oriented?
2. Which boundary is least convincing and why?
3. What failure case still needs a test?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

## References

[FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/) · [GitHub Actions — Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) · [Docker Compose — Compose file reference](https://docs.docker.com/compose/compose-file/)
