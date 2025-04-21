import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import call, patch

from app.api.models import TicketStatusChange
from app.service.event_processing.tracker_events import process_ticket_status_change
from app.service.orm.models import ThreadTicketSub
from app.service.pachca_client import PachcaClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ticket_event", "tracker_status_list"),
    (
        (
            TicketStatusChange(issue_key="BACKLOG-1", status="Закрыт"),
            set(("Закрыт",))
        ),
    ),
)
async def test_process_ticket_status_change(
    ticket_event: TicketStatusChange,
    tracker_status_list: set[str],
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    subs = (
        ThreadTicketSub(
            issue_key=ticket_event.issue_key,
            chat_id=1,
            message_id=1,
        ),
        ThreadTicketSub(
            issue_key=ticket_event.issue_key,
            chat_id=2,
            message_id=2,
        ),
    )
    for sub in subs:
        session.add(sub)
    await session.commit()
    await process_ticket_status_change(
        ticket_event=ticket_event,
        tracker_status_list=tracker_status_list,
        session=session,
        pachca_client=pachca_client,
    )
    pachca_client.send_message.assert_has_calls(
        (
            call(
                chat_id=sub.chat_id,
                text=f"Тикет {sub.issue_key} был переведён в статус {ticket_event.status}",
                parent_message_id=sub.message_id,
            )
            for sub in subs
        ),
        any_order=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ticket_event", "tracker_status_list"),
    (
        (
            TicketStatusChange(issue_key="BACKLOG-1", status="Закрыт"),
            set(("Закрыт",))
        ),
    ),
)
async def test_process_ticket_status_change_does_not_raise(
    ticket_event: TicketStatusChange,
    tracker_status_list: set[str],
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    subs = (
        ThreadTicketSub(
            issue_key=ticket_event.issue_key,
            chat_id=1,
            message_id=1,
        ),
        ThreadTicketSub(
            issue_key=ticket_event.issue_key,
            chat_id=2,
            message_id=2,
        ),
    )
    for sub in subs:
        session.add(sub)
    await session.commit()

    patcher = patch("app.service.pachca_client.PachcaClient.send_message")
    method = patcher.start()
    method.side_effect = (None, Exception())

    # Just checking it does not raise exception
    await process_ticket_status_change(
        ticket_event=ticket_event,
        tracker_status_list=tracker_status_list,
        session=session,
        pachca_client=pachca_client,
    )
