import asyncio
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.router import router
from app.config import AppConfig, get_config
from app.service.orm.sessionmaker import get_session
from app.service.tasks.response_sla_notification import notify_about_pending_questions
from app.service.telegram_client import TelegramClient
from app.service.telegram_client import get_client as get_telegram_client


async def sla_notification_poller(
    session: AsyncSession,
    telegram_client: TelegramClient,
    config: AppConfig,
    check_time: datetime,
) -> None:
    try:
        await notify_about_pending_questions(
            session=session,
            telegram_client=telegram_client,
            config=config,
            check_time=check_time,
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        raise e


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async def periodic_task() -> None:
        config = get_config()
        # very stupid and ugly and causes exception on startup, but I can't take this anymore
        session = await anext(get_session())
        telegram_client = await anext(get_telegram_client())
        while True:
            check_time = datetime.now(tz=timezone.utc)
            try:
                await sla_notification_poller(
                    session=session,
                    telegram_client=telegram_client,
                    config=config,
                    check_time=check_time,
                )
            except Exception:
                logger.error(traceback.format_exc())
                # retry in a short period
                await asyncio.sleep(10)
            else:
                # wait properly
                await asyncio.sleep(config.response_sla_notifications_period_seconds)

    task = asyncio.create_task(periodic_task())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
