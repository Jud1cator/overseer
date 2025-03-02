import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import TicketStatusChange
from app.service.orm.models import ThreadTicketSub
from app.service.pachca_client import PachcaClient


async def process_ticket_status_change(
    ticket_event: TicketStatusChange,
    tracker_status_list: set[str],
    session: AsyncSession,
    pachca_client: PachcaClient,
) -> None:
    if len(tracker_status_list) > 0 and ticket_event.status not in tracker_status_list:
        logger.info("Status %s is not tracked", ticket_event.issue_key)
        return
    stmt = select(ThreadTicketSub).where(
        ThreadTicketSub.issue_key == ticket_event.issue_key
    )
    result = await session.execute(stmt)
    tasks = []
    for sub in result.scalars():
        tasks.append(
            asyncio.create_task(
                pachca_client.send_message(
                    chat_id=sub.chat_id,
                    text=f"Тикет {ticket_event.issue_key} был переведён в статус {ticket_event.status}",
                    parent_message_id=sub.message_id,
                )
            )
        )
    await asyncio.gather(*tasks)
