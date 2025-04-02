import asyncio
from typing import AsyncGenerator
from unittest.mock import patch
import aiohttp

import aiohttp.http_exceptions
import aiohttp.web_exceptions
import pytest_asyncio
from loguru import logger
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.service.orm.models import Base
from app.service.pachca_client.client import PachcaClient


@pytest_asyncio.fixture()
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(url="sqlite+aiosqlite://", echo=True)
    async with engine.connect() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
        await connection.commit()
    yield engine


@pytest_asyncio.fixture()
async def sessionmaker(engine: AsyncEngine) -> AsyncGenerator[async_sessionmaker, None]:
    yield async_sessionmaker(engine)


async def __truncate_tables(session: AsyncSession):
    tasks = []
    for name, table in Base.metadata.tables.items():
        logger.info("Truncate table {}", name)
        tasks.append(session.execute(delete(table)))

    await asyncio.gather(*tasks)
    await session.commit()


@pytest_asyncio.fixture()
async def session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        try:
            await __truncate_tables(session)
            yield session
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture()
async def pachca_client() -> AsyncGenerator[PachcaClient, None]:
    with patch(
        "app.service.pachca_client.PachcaClient.send_message", return_value=None
    ):
        yield PachcaClient(token="test_token")
