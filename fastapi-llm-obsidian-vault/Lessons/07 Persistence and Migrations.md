# Lesson 07 — Persistence and Migrations

## Objective

Persist conversations and messages using PostgreSQL, SQLAlchemy 2.x, and Alembic — without scattering SQL through route handlers.

## The idea in simple terms

Three tools, three jobs:

- **SQLAlchemy** is a translator between Python objects and database rows. You write `message = Message(role="user", content="hi")` and it writes the SQL for you. It does *not* create the tables — that is Alembic's job.
- **Alembic** is version control for your database schema, like git for tables. Each migration file is a committed, reviewable change ("create `message` table") that can be applied (`upgrade`) or undone (`downgrade`).
- **The repository** is a class that is the *only* place in the app that touches the session. Services ask the repository for things in business language (`add_message(...)`, `get_history(...)`) and never see SQL.

New architecture (one more layer than Lesson 06):

```text
Route → Service → Repository → SQLAlchemy session → PostgreSQL
                  ↘ LLM Client → provider
```

The service orchestrates: "save the user message, call the LLM, save the reply." It is the conductor; the repository and LLM client are the players.

## Initial data model

```text
conversation
------------
id          UUID, primary key
created_at  timestamp

message
-------
id               UUID, primary key
conversation_id  foreign key → conversation.id
role             'user' | 'assistant' | 'system'
content          text
created_at       timestamp
```

## Step 1 — Run PostgreSQL in Docker

```bash
docker run -d --name llm-postgres \
  -p 5432:5432 \
  -e POSTGRES_USER=llm \
  -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=llm \
  postgres:16
```

`-d` runs it in the background; `-p 5432:5432` exposes it on localhost. You can throw this container away and start a fresh one any time — that is the point.

## Step 2 — Add dependencies and settings

```bash
poetry add sqlalchemy alembic asyncpg
```

Add to `Settings` in `app/core/config.py` (and copy the names into `.env.example`):

```python
database_url: str = "postgresql+asyncpg://llm:dev@localhost:5432/llm"
```

Note the `+asyncpg` part: it tells SQLAlchemy to use the **async** driver — the one FastAPI needs. Forgetting it makes SQLAlchemy look for the sync driver (`psycopg2`), which isn't installed: `Can't load plugin: sqlalchemy.dialects:postgresql.psycopg2`. Choosing the async driver has a consequence for Alembic — see Step 5, item 3.

### Known quirk on this machine — `poetry add` fails with a network error

On this work machine, `poetry add` may fail with:

```text
All attempts to connect to pypi.org failed.
Probable Causes: the server is not responding / DNS / no internet
```

**None of those three causes is true.** The real story (diagnosed 2026-10-01):

1. Zendesk's Netskope proxy intercepts **all** HTTPS traffic and re-signs every certificate with the corporate CA (`ca.zendesk.goskope.com`). This affects every host, not just pypi.org — public PyPI mirrors get the same certificate, so switching sources does not help.
2. That corporate CA certificate is missing the `keyUsage` extension. Old SSL libraries (this venv's LibreSSL) tolerate it; modern OpenSSL 3.5+ — which Homebrew's Poetry runs on — rejects it: `certificate verify failed: CA cert does not include key usage extension`.
3. Poetry 2.4 cannot be configured around it: certificate settings (`certificates.<repo>.cert`, `verify = false`, `REQUESTS_CA_BUNDLE`) are only read for repositories you explicitly declare. The **default** PyPI source ignores all of them and always verifies strictly.

**How this was diagnosed** (worth remembering as a method):

```bash
curl -sv https://pypi.org/simple/ -o /dev/null 2>&1 | grep -i issuer   # shows the corporate CA, not the real one
poetry add sqlalchemy alembic asyncpg -v                              # the real error, hidden by the friendly message
```

The lesson: **"network error" messages lie.** When the obvious causes don't apply, get the raw error with `-v` before believing the summary.

**Workarounds, in order:**

1. **Run the one command off the corporate network** (hotspot / home wifi). The real pypi.org certificate verifies fine, `pyproject.toml` + `poetry.lock` get updated correctly, and everything after (`poetry install`, tests, running the app) works offline. Poetry only needs the network while *resolving*.
2. **File with IT** — the malformed CA breaks every OpenSSL 3.5+ tool (Homebrew Python, Poetry, Node…), not just this. Ask about an internal PyPI mirror (often in Artifactory) or a fixed CA. Give them the exact string: `CA cert does not include key usage extension`.
3. **Stopgap only** (breaks the lock discipline of this project):
   ```bash
   REQUESTS_CA_BUNDLE=~/.certs/corporate-cas.pem poetry run pip install sqlalchemy alembic asyncpg
   ```
   The venv's old LibreSSL accepts the corporate CA (`~/.certs/corporate-cas.pem` was exported 2026-10-01 for this). But pip does **not** update `poetry.lock` — regenerate it on a clean network later.

## Step 3 — Create the database module

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)
```

```python
# app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

## Step 4 — Define the models

```python
# app/db/models.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "message"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id"))
    role: Mapped[str] = mapped_column(String(16))   # 'user' | 'assistant' | 'system'
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
```

`Mapped[...]` type hints are how SQLAlchemy 2.x reads your intent: `Mapped[str]` → text column, `Mapped[uuid.UUID]` → UUID column. Models describe structure; they never connect to the database themselves.

## Step 5 — Set up Alembic

```bash
poetry run alembic init migrations
```

Then edit two things in `migrations/env.py`:

1. Import your models' metadata so autogenerate can see them:

```python
from app.db.base import Base
from app.db import models  # noqa: F401 — imports register the models

target_metadata = Base.metadata
```

2. Override the hardcoded `sqlalchemy.url` with your settings. First, understand what you're changing: `alembic init` created `alembic.ini` with a placeholder line `sqlalchemy.url = driver://user:pass@localhost/dbname`. Don't edit that line — `alembic.ini` is committed to git (a password would live in your repo forever), and a URL there would become a second source of truth alongside `Settings`. Instead, override it **in memory** a t the top of `migrations/env.py`, right after `config = context.config` (NOT inside `run_migrations_online` — placing it at the top means both the offline and online code paths pick it up):

```python
# migrations/env.py — with your other app imports near the top:
from app.core.config import settings

# ... then, immediately after this existing line:
config = context.config
# add this one:
config.set_main_option("sqlalchemy.url", settings.database_url)
```

`set_main_option` means: "whatever `alembic.ini` says for `sqlalchemy.url`, use this instead." The chain becomes `.env` → `Settings` → `env.py` → Alembic → PostgreSQL — the same one source of truth the app uses.

3. Make `run_migrations_online` async. The default `env.py` template is written for **sync** drivers. Our URL is async (`asyncpg`), so the default template fails with:

   ```text
   sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call
   await_only() here. Was IO attempted in an unexpected place?
   ```

   Meaning: sync code tried to touch the async driver's world. The fix is the async version of `run_migrations_online` (this is what `alembic init -t async` generates — written out here so you can see what changes). At the top of `env.py`, alongside the other imports:

   ```python
   import asyncio

   from sqlalchemy import pool
   from sqlalchemy.ext.asyncio import async_engine_from_config
   ```

   Then replace the whole `run_migrations_online` function:

   ```python
   def run_migrations_online() -> None:
       """Run migrations in 'online' mode with the async driver."""
       connectable = async_engine_from_config(
           config.get_section(config.config_ini_section, {}),
           prefix="sqlalchemy.",
           poolclass=pool.NullPool,
       )

       def do_run_migrations(connection) -> None:
           context.configure(
               connection=connection, target_metadata=target_metadata
           )

           with context.begin_transaction():
               context.run_migrations()

       async def run_async_migrations() -> None:
           async with connectable.connect() as connection:
               await connection.run_sync(do_run_migrations)

       asyncio.run(run_async_migrations())
   ```

   What changed: `engine_from_config` (sync) → `async_engine_from_config` (async), and the connection work is wrapped in `asyncio.run(...)` — a tiny event loop for the migration run — with `connection.run_sync(...)` as the official hop between the async connection and Alembic's sync migration code.

Generate and apply the first migration:

```bash
poetry run alembic revision --autogenerate -m "create conversation and message tables"
poetry run alembic upgrade head
```

**Always open the generated file in `migrations/versions/` and read it before applying.** Autogenerate is good but not perfect — it can miss renames (it sees drop + add, which loses data). Treat a migration like a commit message: review it, then apply it.

## Step 6 — Create the repository

```python
# app/repositories/chat.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self) -> Conversation:
        conversation = Conversation()
        self._session.add(conversation)
        await self._session.commit()
        return conversation

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: str
    ) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self._session.add(message)
        await self._session.commit()
        return message

    async def get_history(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars())
```

Notice: the repository takes the session in its constructor, exactly like `ChatService` takes an `LLMClient`. Same pattern, new dependency.

## Step 7 — Wire it up

The service gains an **optional** repository (constructor injection again). Full file, with four details the simple sketch hides:

```python
# app/services/chat.py
from __future__ import annotations   # makes X | None syntax legal on Python 3.9

import uuid

from app.llm.client import LLMClient
from app.repositories.chat import ChatRepository


class ChatService:
    def __init__(
        self,
        llm_client: LLMClient,
        repository: ChatRepository | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._repository = repository

    async def reply(
        self, user_message: str, conversation_id: uuid.UUID | None = None
    ) -> str:
        if self._repository is not None:
            if conversation_id is None:
                conversation = await self._repository.create_conversation()
                conversation_id = conversation.id
            await self._repository.add_message(
                conversation_id, "user", user_message
            )

        prompt = self._build_prompt(user_message)
        reply = await self._llm_client.generate(prompt)

        if self._repository is not None:
            await self._repository.add_message(conversation_id, "assistant", reply)
        return reply

    @staticmethod
    def _build_prompt(user_message: str) -> str:
        return f"You are a helpful assistant.\nUser: {user_message}"
```

The four details, and why each matters:

1. **`from __future__ import annotations`** must be the first line — without it, `uuid.UUID | None` crashes on import with `TypeError: unsupported operand type(s) for |` on Python 3.9 (this project supports `>=3.9`).
2. **`import uuid`** — the annotation uses it; forgetting the import gives `NameError` at import time.
3. **Defaults of `None` on both new parameters** — backward compatibility in your own code: the route still calls `service.reply(request.message)`, the old unit tests still call `reply("hello")`, and both keep working unchanged. Run `poetry run pytest -q` after this edit: if all tests still pass with zero test edits, the defaults did their job.
4. **The `if self._repository is not None` guards** — persistence is optional; without a repository, chat still works (only the LLM round-trip happens). A naive version calls `add_message` unconditionally and crashes with `AttributeError`/`None` when no repository was injected.

Common edit-order mistake when adapting this file by hand: pasting the new `reply` body at the wrong indentation level gives `IndentationError: expected an indented block` — Python has no braces, indentation *is* the structure, so the body must sit one level deeper than its `def`.

**Where this stands (2026-10-05):** the service accepts an optional repository and the repository, session factory, models, and first migration all exist and are applied — **but `get_chat_service` does not pass a repository yet**, so live chats are not saved to Postgres. Every piece is built; the remaining work is exactly two lines of wiring: construct `ChatRepository(session)` from the `get_session` dependency and pass it into `ChatService`, then thread a `conversation_id` through the chat request/response schemas if the API should continue conversations. That is the first task of the next work session — and a good review exercise, because it exercises every layer at once. See [[Lessons/11 Architecture Walkthrough|Lesson 11]] Part 4 Step 9.

The dependency provider in `app/api/dependencies.py` opens a session per request and closes it afterwards:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionFactory


async def get_session() -> AsyncSession:
    async with SessionFactory() as session:
        yield session
```

`yield` inside a FastAPI dependency means: hand this to the route now, run the cleanup (closing the session) after the response.

## Step 8 — Test without a database

Before fighting with a real database in tests, fake the repository the same way you fake the LLM client:

```python
class FakeChatRepository:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def create_conversation(self):
        return SimpleNamespace(id=uuid.uuid4())

    async def add_message(self, conversation_id, role, content):
        self.messages.append((role, content))

    async def get_history(self, conversation_id):
        return []
```

Assert that after `service.reply("hi")`, `fake_repository.messages == [("user", "hi"), ("assistant", <the fake reply>)]`. This proves the workflow saves both sides of the conversation with zero infrastructure.

A real-database integration test (create → reply → read history) comes at the end of the lesson, in `tests/integration/`, against a throwaway Postgres container — never your development database.

## Commands

```bash
poetry add sqlalchemy alembic asyncpg
poetry run alembic revision --autogenerate -m "create conversation and message tables"
poetry run alembic upgrade head
poetry run pytest -q
```

## Common mistakes

- **Believing Poetry's "network error" summary on this machine** — behind the corporate proxy it hides an SSL certificate failure; see the "Known quirk" section under Step 2 before debugging DNS or wifi.
- **Forgetting `+asyncpg` in the URL** — SQLAlchemy silently uses the sync driver and you get confusing greenlet errors.
- **`the greenlet library is required to use this function`** during `alembic revision` — the async driver is present but the greenlet bridge library isn't installed. Alembic's `env.py` is synchronous code driving an async driver; greenlet is how sync code steps into async. It is a transitive dependency of SQLAlchemy — the fix is `pip install greenlet` (stopgap) or a proper `poetry add sqlalchemy`, which pulls it automatically.
- **`greenlet_spawn has not been called` during `alembic revision`** — a different greenlet error: the default (sync) `env.py` template is driving the async `asyncpg` URL. The fix is the async `run_migrations_online` (Step 5, item 3). Greenlet errors come in two flavors: "library is required" = greenlet isn't installed; "greenlet_spawn has not been called" = sync code reached the async driver without the async scaffolding.
- **Committing inside the repository *and* the service** — pick one transaction boundary (see mentor question 2) or you get half-saved conversations.
- **Applying autogenerated migrations unread** — autogenerate can propose destructive changes (drop column) for what was actually a rename.
- **Testing against your development database** — one bad test run can wipe real data. Separate database or schema, always.

## Checkpoint

- [ ] Postgres runs in Docker and `psql` (or a GUI) can connect.
- [ ] `Settings.database_url` is typed, with a default for local dev; `.env.example` updated.
- [ ] Models exist for `conversation` and `message`; no SQL strings anywhere outside the repository.
- [ ] First Alembic migration generated, **read**, applied.
- [ ] `ChatRepository` takes an `AsyncSession` in its constructor.
- [ ] The service test uses a fake repository — no database needed.
- [ ] One integration test runs against a real throwaway database.

## Mentor questions

1. Is a repository abstraction useful for each operation, or only the ones reused across services?
2. Where should transaction boundaries live — repository method, service call, or request? (Hint: what happens if the LLM call fails after the user message is saved?)
3. How should a database session be closed after a request? (We did it with `yield` — what are the alternatives?)

## Progress

- Status: **In progress — database pieces exist, live repository wiring and integration testing remain**
- Completed: [x] models [x] async session [x] migration [x] repository boundary [ ] inject repository into chat [ ] real database integration test
- Date:

## References

[SQLAlchemy 2.0 Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) · [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/) · [FastAPI — Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)

## Review note

The lesson covers the database model, async session, migration, and repository boundaries. The live chat path still does not inject `ChatRepository`, and no real database integration test is checked in yet. Those are deliberate next steps, not reasons to move SQL into the route.
