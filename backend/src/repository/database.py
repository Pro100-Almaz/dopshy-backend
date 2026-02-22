from sqlalchemy.ext.asyncio import (
    async_sessionmaker as sqlalchemy_async_sessionmaker,
    AsyncEngine as SQLAlchemyAsyncEngine,
    AsyncSession as SQLAlchemyAsyncSession,
    create_async_engine as create_sqlalchemy_async_engine,
)
from sqlalchemy.engine import URL as SQLAlchemyURL
from sqlalchemy.pool import Pool as SQLAlchemyPool

from src.config.manager import settings


class AsyncDatabase:
    def __init__(self):
        # Use SQLAlchemy's URL builder to avoid Pydantic-v1 style DSN construction
        # and to guarantee an asyncpg driver is used.
        # IMPORTANT: do not cast URL to `str()` here.
        # `str(SQLAlchemyURL(...))` intentionally renders the password as "***" for safety.
        # If you pass that string to SQLAlchemy, it will literally try to login with password "***".
        self.postgres_url: SQLAlchemyURL = SQLAlchemyURL.create(
            drivername="postgresql+asyncpg",
            username=settings.DB_POSTGRES_USERNAME,
            password=settings.DB_POSTGRES_PASSWORD,
            host=settings.DB_POSTGRES_HOST,
            port=settings.DB_POSTGRES_PORT,
            database=settings.DB_POSTGRES_NAME,
        )

        print('*'*10)
        print(settings.DB_POSTGRES_PASSWORD)
        print('*'*10)

        self.async_engine: SQLAlchemyAsyncEngine = create_sqlalchemy_async_engine(
            url=self.postgres_url,
            echo=settings.IS_DB_ECHO_LOG,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_POOL_OVERFLOW,
        )
        # Create sessions per-request (do NOT share a single AsyncSession globally).
        self.async_sessionmaker: sqlalchemy_async_sessionmaker[SQLAlchemyAsyncSession] = (
            sqlalchemy_async_sessionmaker(
                bind=self.async_engine,
                expire_on_commit=settings.IS_DB_EXPIRE_ON_COMMIT,
            )
        )
        self.pool: SQLAlchemyPool = self.async_engine.pool


async_db: AsyncDatabase = AsyncDatabase()
