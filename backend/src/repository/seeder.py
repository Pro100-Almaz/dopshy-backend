import sqlalchemy
import loguru
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.manager import settings
from src.models.db.account import Account
from src.models.enums.role import Role
from src.securities.hashing.password import pwd_generator


async def seed_admin(session: AsyncSession) -> None:
    if not settings.ADMIN_USERNAME or not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        loguru.logger.warning("ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD not set — skipping admin seed")
        return

    stmt = sqlalchemy.select(Account).where(Account.email == settings.ADMIN_EMAIL)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        loguru.logger.info(f"Admin '{settings.ADMIN_EMAIL}' already exists — skipping seed")
        return

    admin = Account(
        username=settings.ADMIN_USERNAME,
        email=settings.ADMIN_EMAIL,
        role=Role.ADMIN.value,
        is_verified=True,
        is_active=True,
        is_logged_in=False,
    )
    admin.set_hash_salt(hash_salt=pwd_generator.generate_salt)
    admin.set_hashed_password(
        hashed_password=pwd_generator.generate_hashed_password(
            hash_salt=admin.hash_salt,
            new_password=settings.ADMIN_PASSWORD,
        )
    )
    session.add(admin)
    await session.commit()

    loguru.logger.info(f"Admin account '{settings.ADMIN_EMAIL}' seeded successfully!")
