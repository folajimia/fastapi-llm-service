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

Note the `+asyncpg` part: it tells SQLAlchemy to use the async driver. Forgetting it is the classic "greenlet_spawn has not been called" error.

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

2. Replace the hardcoded `sqlalchemy.url` with your settings (look for the `run_migrations_online` function):

```python
from app.core.config import settings

config.set_main_option("sqlalchemy.url", settings.database_url)
```

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

The service gains an optional repository (constructor injection again):

```python
# app/services/chat.py — sketch of the new reply flow
async def reply(self, user_message: str, conversation_id: uuid.UUID | None) -> str:
    if conversation_id is None and self._repository is not None:
        conversation = await self._repository.create_conversation()
        conversation_id = conversation.id
    await self._repository.add_message(conversation_id, "user", user_message)
    prompt = self._build_prompt(user_message)
    reply = await self._llm_client.generate(prompt)
    await self._repository.add_message(conversation_id, "assistant", reply)
    return reply
```

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

- **Forgetting `+asyncpg` in the URL** — SQLAlchemy silently uses the sync driver and you get confusing greenlet errors.
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

- Status: **Not started**
- Completed: [ ]
- Date:

## References

[SQLAlchemy 2.0 Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) · [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/) · [FastAPI — Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
