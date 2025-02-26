import asyncio
import os
import re

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import PachcaMessage, TicketStatusChange
from app.config import AppConfig, get_config
from app.service.orm.models import ThreadTicketSub
from app.service.orm.sessionmaker import get_session
from app.service.pachca_client import PachcaClient

router = APIRouter()


@router.post("/subscribe")
async def subscribe(
    message: PachcaMessage,
    config: AppConfig = Depends(get_config),
    session: AsyncSession = Depends(get_session),
):
    issue_key = re.findall(f"{config.tracker_queue_key}-\\d+", message.content)
    if len(issue_key) == 0:
        raise ValueError("No issue key found")
    issue_key = issue_key[0]
    sub = ThreadTicketSub(
        issue_key=issue_key,
        chat_id=message.chat_id,
        message_id=message.id,
    )
    session.add(sub)
    await session.commit()
    async with PachcaClient(token=os.environ["PACHCA_TOKEN"]) as client:
        await client.send_message(
            chat_id=message.chat_id,
            text=f"Я сообщу вам об изменении статуса тикета {issue_key}",
            parent_message_id=message.id,
        )


@router.post("/unsubscribe")
async def unsubscribe(
    message: PachcaMessage,
    config: AppConfig = Depends(get_config),
    session: AsyncSession = Depends(get_session),
):
    issue_key = re.findall(f"{config.tracker_queue_key}-\\d+", message.content)
    if len(issue_key) == 0:
        raise ValueError("No issue key found")
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
    async with PachcaClient(token=os.environ["PACHCA_TOKEN"]) as client:
        await client.send_message(
            chat_id=message.chat_id,
            text=f"Тикет {issue_key} больше не отслеживается в этом треде",
            parent_message_id=message.id,
        )


@router.post("/ticket_status_change")
async def ticket_status_change(
    ticket_event: TicketStatusChange,
    config: AppConfig = Depends(get_config),
    session: AsyncSession = Depends(get_session),
):
    if (
        len(config.tracker_status_list) > 0
        and ticket_event.status not in config.tracker_status_list
    ):
        return f"Status {ticket_event.issue_key} is not tracked"
    stmt = select(ThreadTicketSub).where(
        ThreadTicketSub.issue_key == ticket_event.issue_key
    )
    result = await session.execute(stmt)
    tasks = []
    async with PachcaClient(token=os.environ["PACHCA_TOKEN"]) as client:
        for sub in result.scalars():
            tasks.append(
                asyncio.create_task(
                    client.send_message(
                        chat_id=sub.chat_id,
                        text=f"Тикет {ticket_event.issue_key} был переведён в статус {ticket_event.status}",
                        parent_message_id=sub.message_id,
                    )
                )
            )
        await asyncio.gather(*tasks)
