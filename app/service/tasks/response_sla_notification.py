from datetime import datetime, timedelta, timezone

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
    msg_links = []
    for msg in sorted(groups.values(), key=lambda m: m.created_at):
        if msg.thread_message_id is None:
            msg_links.append(f"https://app.pachca.com/chats/{msg.chat_id}?message={msg.message_id}")
        else:
            msg_links.append(
                f"https://app.pachca.com/chats?thread_message_id={msg.thread_message_id}&sidebar_message={msg.message_id}"
            )
    msg_text = f"Сообщения ожидающие реакции:\n\n{'\n\n'.join(msg_links)}"
    await telegram_client.send_message(chat_id=config.telegram_chat_id, message=msg_text)
