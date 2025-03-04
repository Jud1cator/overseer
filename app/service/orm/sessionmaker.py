import os
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

sessionmaker = async_sessionmaker(
    bind=create_async_engine(url=os.environ["STORAGE_DSN"], echo=True)
)
logger.info("Engine created because of the import")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
