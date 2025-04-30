import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from loguru import logger
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import AppConfig
from app.service.orm.models import Base
from app.service.pachca_client.client import PachcaClient
from app.service.telegram_client.client import TelegramClient


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
    with patch("app.service.pachca_client.PachcaClient.send_message", return_value=None):
        yield PachcaClient(token="test_token")


@pytest_asyncio.fixture()
async def telegram_client() -> AsyncGenerator[TelegramClient, None]:
    with patch.multiple(
        "app.service.telegram_client.TelegramClient",
        __init__=lambda *args, **kwargs: None,  # aiogram validates token right away, so we have to mock init
        send_message=AsyncMock(return_value=None),
    ):
        yield TelegramClient(token="test_token")


@pytest_asyncio.fixture()
async def app_config() -> AsyncGenerator[AppConfig, None]:
    yield AppConfig(
        pachca_token="default_token",
        telegram_token="default_token",
        telegram_chat_id=-1,
        tracker_queue_key="TEST",
        tracker_status_list=set(("Closed",)),
        message_group_time_frame_seconds=10,
    )
