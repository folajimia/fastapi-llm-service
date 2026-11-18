# Lesson 10 — Docker, CI, and Final Review

## Objective

Make the service reproducible for another developer (and a server) and prevent broken changes from reaching the main branch.

## The idea in simple terms

"Works on my machine" is not done. Done means: a clean checkout on a fresh machine runs with the documented commands. Two tools enforce that:

- **Docker** packages the app plus its exact Python environment into an image that behaves identically everywhere.
- **CI** (GitHub Actions) re-runs your checks on every push and pull request, so a broken change is caught before merge — including changes you forgot to test locally.

## Step 1 — Understand the two-container setup

There are two containers, each with one job:

```text
Your Mac                         Podman Compose network
curl localhost:8000  ────────►  api (FastAPI, built from Dockerfile)
                                      │
                                      └────► db (PostgreSQL image)
```

The **Dockerfile builds the API image**. PostgreSQL comes from the official `postgres:16` image, so this project does not need a database Dockerfile. `docker-compose.yml` (run with Docker Compose or `podman compose`) starts both containers and connects them.

## Step 2 — Declare and lock the Python dependencies

The API imports FastAPI, Pydantic settings, SQLAlchemy, `asyncpg`, HTTPX, and the Anthropic adapter. Alembic is needed to run migrations. These packages must be listed under the main dependencies in `pyproject.toml`; packages listed only under `dev` are not installed by the Dockerfile's `--only main` command.

After changing dependencies, regenerate the lock file using the same Poetry version as the Dockerfile. This project's Dockerfile pins Poetry 2.4.3:

```bash
poetry --version
poetry lock
```

The lock file records exact package versions. `pyproject.toml` and `poetry.lock` must agree before Docker can install them.

## Step 3 — Build the API image

The important parts of this project's `Dockerfile` are:

```dockerfile
FROM python:3.12-slim

ENV POETRY_VERSION=2.4.3 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

RUN pip install "poetry==${POETRY_VERSION}"
WORKDIR /app

# Install dependencies first so code-only changes can reuse this layer.
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# The API and Alembic migration files are needed in the image.
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The `.dockerignore` keeps `.env`, `.venv`, Git data, and the lesson vault out of the image. Excluding `.env` is important because it may contain secrets.

## Step 4 — Compose starts the API and PostgreSQL

The root `docker-compose.yml` defines these services:

```yaml
services:
  api:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://llm:dev@db:5432/llm
      LLM_PROVIDER: ${LLM_PROVIDER:-demo}
      LLM_API_KEY: ${LLM_API_KEY:-}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: llm
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: llm
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U llm"]
      interval: 5s
      retries: 5
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

`api.build: .` builds the API from the Dockerfile. `db.image: postgres:16` uses the standard PostgreSQL image; no custom database Dockerfile is required. Compose puts both services on a private network. The API uses hostname `db` because that is the database service name. Inside a container, `localhost` means that same container, not your Mac or another container.

The database health check makes Compose wait until PostgreSQL accepts connections before starting the API. The named `pgdata` volume keeps database files when containers stop or are replaced. `down -v` deletes that data, so use it only when you intend to reset the local database. The `dev` database password is for learning locally; use managed secrets for a deployed service.

## Step 5 — Start, migrate, and test the service

Run from the repository root. On a Mac using Podman, install the Compose provider once if needed:

```bash
brew install podman-compose
```

Build the API image and start both containers:

```bash
poetry lock
podman compose up --build -d
podman compose ps
podman compose logs api
```

Both services should be running. The API should show a host port mapping for `8000`. Apply the database schema from inside the API container:

```bash
podman compose exec api poetry run alembic upgrade head
```

Open `http://localhost:8000/docs`, or check the health endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

`curl` runs on your Mac; the response comes from the API container through the `8000:8000` port mapping. To confirm, check `podman compose ps` for the running API and follow its request logs with `podman compose logs -f api` while sending the curl request.

Stop the containers and keep database data with:

```bash
podman compose down
```

Start them again with `podman compose up -d`. To delete database data too, use `podman compose down -v` deliberately.

## Step 6 — Problems we encountered and how to fix them

| Error or symptom | Why it happens | Fix |
|---|---|---|
| `pyproject.toml changed significantly since poetry.lock was last generated` | Dependencies changed without refreshing the lock, or the lock was generated using a different Poetry version. | Use Poetry 2.4.3 to match the Dockerfile and run `poetry lock`, then rebuild. |
| `no context directory and no Containerfile specified` | The build command omitted its context directory. | Add `.`: `podman build -t llm-service .`. |
| `looking up compose provider failed` | `podman compose` is a wrapper and no Compose provider is installed. | On macOS run `brew install podman-compose`. |
| `podman compose ps -a` prints usage | The installed `podman-compose` version does not accept `-a` after `ps`. | Use `podman compose ps`; to include stopped containers, use `podman ps -a`. |
| `can only create exec sessions on running containers` | The API container exited. `exec` only works in a running container. | Check `podman compose ps` and `podman compose logs api`; fix the startup error, rebuild, and restart. |
| `ModuleNotFoundError: No module named 'sqlalchemy'` (or another package) | The package is missing from main dependencies, or the image predates the dependency update. | Add it to `pyproject.toml`, run `poetry lock`, and rebuild the API. |
| Alembic cannot find `alembic.ini` or `migrations` | Those files were not copied into the API image. | Keep both `COPY` lines in the Dockerfile and rebuild after migration-file changes. |
| Alembic reports missing revision `e6e41524117d` | A migration's `down_revision` points to a revision that has no file. Here, the empty migration `33c19af18da8` should follow the existing schema migration `9cb4d0faf08e`. | Set `down_revision` in the newer file to `9cb4d0faf08e`; check that every parent revision exists. |
| The same migration error remains after editing the file | The running container still has the old image. Host edits do not update an existing image. | Run `podman compose build --no-cache api`, then `podman compose up -d --force-recreate`. Verify the file inside the container before retrying Alembic. |
| API cannot connect to the database using `localhost` | `localhost` inside the API container points back to the API container. | Use `db` as the database hostname in `DATABASE_URL`. |
| Chat returns a database table error | Migrations have not been applied yet. | Run `podman compose exec api poetry run alembic upgrade head`. |

Useful diagnostics:

```bash
podman compose ps
podman compose logs api
podman ps -a
podman compose exec api poetry run alembic current
```

## Step 7 — Clean-checkout walkthrough

From a fresh clone, the main workflow should be understandable from the README and these commands:

```bash
poetry install
poetry lock
podman compose up --build -d
podman compose exec api poetry run alembic upgrade head
curl http://localhost:8000/api/v1/health
podman compose down
```

If a step requires undocumented knowledge, add it to the README so the next developer can follow the same path.

## Step 8 — GitHub Actions CI

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

## Step 9 — README as the front door

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
- **Using `localhost` for the database host in Compose** — inside the API container, use the Compose service name (`db`).
- **Expecting `compose down` to erase data** — named volumes persist; use `down -v` only when you intend to delete the local database.
- **Running migrations in the wrong environment** — `podman compose exec api ...` runs them in the API container against the Compose database.
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
