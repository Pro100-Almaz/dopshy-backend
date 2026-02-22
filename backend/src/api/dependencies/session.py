import typing

from sqlalchemy.ext.asyncio import (
    AsyncSession as SQLAlchemyAsyncSession,
)

from src.repository.database import async_db


async def get_async_session() -> typing.AsyncGenerator[SQLAlchemyAsyncSession, None]:
    # A new session per request; context manager guarantees close.
    async with async_db.async_sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
