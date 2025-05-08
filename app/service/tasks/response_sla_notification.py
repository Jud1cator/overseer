import asyncio
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppConfig
from app.service.orm.models import StudentMessage
from app.service.telegram_client import TelegramClient


async def notify_about_pending_questions(
    session: AsyncSession,
    telegram_client: TelegramClient,
    config: AppConfig,
    check_time: datetime = datetime.now(tz=timezone.utc),
) -> None:
    stmt = (
        select(StudentMessage)
        .where(~StudentMessage.received_reaction)
        .where(StudentMessage.sent_at <= check_time - timedelta(seconds=config.response_sla_seconds))
    )
    result = (await session.execute(stmt)).scalars().all()
    if len(result) == 0:
        logger.info("There are no pending questions with violated SLA.")
        return
    groups: dict[int, StudentMessage] = {}
    for message in result:
        if message.message_group_id in groups:
            cur_msg = groups[message.message_group_id]
            if message.created_at < cur_msg.created_at:
                groups[message.message_group_id] = message
        else:
            groups[message.message_group_id] = message
    logger.info(f"Pending message groups: {len(groups)}")
    tasks = []
    for course in ("HardDE", "StartDE"):
        msg_links = []
        for msg in sorted(filter(lambda msg: msg.course == course, groups.values()), key=lambda m: m.created_at):
            if msg.thread_message_id is None:
                msg_links.append(f"https://app.pachca.com/chats/{msg.chat_id}?message={msg.message_id}")
            else:
                msg_links.append(
                    f"https://app.pachca.com/chats?thread_message_id={msg.thread_message_id}&sidebar_message={msg.message_id}"
                )
            logger.info(f"Message {msg.message_id} is added to notification list")
        msg_text = f"#{course}: сообщения ожидающие реакции:\n\n{'\n\n'.join(msg_links)}"
        msk_dttm = check_time.astimezone(ZoneInfo("Europe/Moscow"))
        if (
            len(msg_links) > 0
            and (
                (
                    course == "HardDE"
                    and (time(10, 0) <= msk_dttm.time() <= time(14, 55) or time(17, 0) <= msk_dttm.time() <= time(21, 55))
                )
                or
                (
                    course == "StartDE"
                    and (
                        msk_dttm.weekday() in {0, 1}
                        and time(17, 0) <= msk_dttm.time() <= time(21, 55)
                        or msk_dttm.weekday() in {2, 3, 4}
                        and (time(10, 0) <= msk_dttm.time() <= time(14, 55) or time(17, 0) <= msk_dttm.time() <= time(21, 55))
                    )
                )
            )
        ):
            logger.info(f"Sending notification for {course}: {msg_text}")
            tasks.append(
                asyncio.create_task(telegram_client.send_message(chat_id=config.telegram_chat_id, message=msg_text))
            )
        else:
            logger.info(f"Not sending notification for {course} because it is not shift time")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    n_exceptions = sum(1 if isinstance(r, Exception) else 0 for r in results)
    if n_exceptions > 0:
        logger.warning(
            "Some errors were encountered while trying to send messages, {}/{} requests failed.".format(
                n_exceptions, len(results)
            )
        )
        for r in results:
            if isinstance(r, Exception):
                logger.error(r)
