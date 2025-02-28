import pytest

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

sessionmaker = async_sessionmaker(
    bind=create_async_engine(url="sqlite")
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@pytest.fixture
def session():
