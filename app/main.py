import asyncio
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from app.api.router import router
from app.config import get_config
from app.service.orm.sessionmaker import sessionmaker
from app.service.tasks.response_sla_notification import notify_about_pending_questions
from app.service.telegram_client import get_client as get_telegram_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async def periodic_task() -> None:
        logger.info("Notification poller started")
        while True:
            check_time = datetime.now(tz=timezone.utc)
            logger.info(f"Current time is {check_time}")
            try:
                config = get_config()
                telegram_client = await anext(get_telegram_client())
                async with sessionmaker() as session:
                    await notify_about_pending_questions(
                        session=session,
                        telegram_client=telegram_client,
                        config=config,
                        check_time=check_time,
                    )
                logger.info("Notifications sent successfully")
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
