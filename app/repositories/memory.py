from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserFact


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> dict[str, str]:
        result = await self._session.execute(select(UserFact))
        return {fact.key: fact.value for fact in result.scalars()}

    async def set_fact(self, key: str, value: str) -> None:
        fact = await self._session.get(UserFact, key)
        if fact is None:
            fact = UserFact(key=key, value=value)
            self._session.add(fact)
        else:
            fact.value = value
        await self._session.commit()