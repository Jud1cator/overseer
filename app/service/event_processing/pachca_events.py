import re

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import PachcaMessage
from app.service.orm.models import ThreadTicketSub
from app.service.pachca_client import PachcaClient


async def process_subscribe(
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
) -> None:
    issue_key = re.findall(f"{tracker_queue_key}-\\d+", message.content)
    if len(issue_key) == 0:
        logger.info("No issue key found in {}", message.content)
        return
    issue_key = issue_key[0]
    sub = ThreadTicketSub(
        issue_key=issue_key,
        chat_id=message.chat_id,
        message_id=message.id,
    )
    session.add(sub)
    await session.commit()
    await pachca_client.send_message(
        chat_id=message.chat_id,
        text=f"Я сообщу вам об изменении статуса тикета {issue_key}",
        parent_message_id=message.id,
    )


async def process_unsubscribe(
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
) -> None:
    issue_key = re.findall(f"{tracker_queue_key}-\\d+", message.content)
    if len(issue_key) == 0:
        logger.info("No issue key found in {}", message.content)
        return
    issue_key = issue_key[0]
    stmt = (
        select(ThreadTicketSub)
        .where(ThreadTicketSub.issue_key == issue_key)
        .where(ThreadTicketSub.chat_id == message.chat_id)
    )
    result = await session.execute(stmt)
    sub = result.scalars().one()
    await session.delete(sub)
    await session.commit()
    await pachca_client.send_message(
        chat_id=message.chat_id,
        text=f"Тикет {issue_key} больше не отслеживается в этом треде",
        parent_message_id=message.id,
    )
