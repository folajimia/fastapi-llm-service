# FROM python:3.11-slim

# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1 \
#     POETRY_VERSION=2.4.2 \
#     POETRY_HOME=/opt/poetry \
#     POETRY_NO_INTERACTION=1 \
#     PATH="/opt/poetry/bin:$PATH"

# RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# WORKDIR /app
# COPY pyproject.toml poetry.lock ./
# RUN poetry install --only main --no-root
# COPY app ./app

# EXPOSE 8000
# CMD ["poetry", "run", "gunicorn", "app.main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]

FROM python:3.12-slim

ENV POETRY_VERSION=2.4.3 \
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
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
