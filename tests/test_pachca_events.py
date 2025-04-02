from datetime import datetime, timezone

import pytest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import PachcaMessage, ThreadInfo
from app.service.event_processing.pachca_events import process_subscribe, process_unsubscribe
from app.service.orm.models import ThreadTicketSub
from app.service.pachca_client import PachcaClient


def pachca_message_factory(
    id=1,
    type="default_type",
    event="default_event",
    entity_type="default_event_type",
    entity_id=1,
    content="default_content",
    user_id=1,
    created_at=datetime.now(timezone.utc),
    chat_id=1,
    parent_message_id=1,
    thread=ThreadInfo(
        message_id=1,
        message_chat_id=1,
    ),
):
    return PachcaMessage(
        type=type,
        id=id,
        event=event,
        entity_type=entity_type,
        entity_id=entity_id,
        content=content,
        user_id=user_id,
        created_at=created_at,
        chat_id=chat_id,
        parent_message_id=parent_message_id,
        thread=thread,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/subscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_subscribe(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    await process_subscribe(
        message=message,
        tracker_queue_key=tracker_queue_key,
        session=session,
        pachca_client=pachca_client,
    )
    stmt = (
        select(ThreadTicketSub)
        .where(ThreadTicketSub.issue_key == issue_key)
        .where(ThreadTicketSub.chat_id == message.chat_id)
    )
    result = await session.execute(stmt)
    sub = result.scalars().one()
    assert sub.issue_key == issue_key
    assert sub.chat_id == message.chat_id
    assert sub.message_id == message.id
    pachca_client.send_message.assert_called_with(
        chat_id=message.chat_id,
        text=f"Я сообщу вам об изменении статуса тикета {issue_key}",
        parent_message_id=message.id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/unsubscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_unsubscribe(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    sub = ThreadTicketSub(
        issue_key=issue_key,
        chat_id=message.chat_id,
        message_id=message.id,
    )
    session.add(sub)
    await session.commit()
    await process_unsubscribe(
        message=message,
        tracker_queue_key=tracker_queue_key,
        session=session,
        pachca_client=pachca_client,
    )
    stmt = (
        select(ThreadTicketSub)
        .where(ThreadTicketSub.issue_key == issue_key)
        .where(ThreadTicketSub.chat_id == message.chat_id)
    )
    result = await session.execute(stmt)
    assert len(result.scalars().all()) == 0
    pachca_client.send_message.assert_called_with(
        chat_id=message.chat_id,
        text=f"Тикет {issue_key} больше не отслеживается в этом треде",
        parent_message_id=message.id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/unsubscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_subscribe_already_subscribed(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    for _ in range(2):
        await process_subscribe(
            message=message,
            tracker_queue_key=tracker_queue_key,
            session=session,
            pachca_client=pachca_client,
        )
    pachca_client.send_message.assert_called_with(
        chat_id=message.chat_id,
        text=f"Тикет {issue_key} уже отслеживается в этом треде",
        parent_message_id=message.id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/unsubscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_unsubscribe_non_existing(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    await process_unsubscribe(
        message=message,
        tracker_queue_key=tracker_queue_key,
        session=session,
        pachca_client=pachca_client,
    )
    pachca_client.send_message.assert_called_with(
        chat_id=message.chat_id,
        text=f"Тикет {issue_key} не отслеживался в этом треде",
        parent_message_id=message.id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/subscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_subscribe_is_transactional_with_broken_orm(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    patcher = patch("sqlalchemy.ext.asyncio.AsyncSession.add")
    patcher.start().side_effect = Exception()
    try:
        await process_subscribe(
            message=message,
            tracker_queue_key=tracker_queue_key,
            session=session,
            pachca_client=pachca_client,
        )
    except Exception:
        patcher.stop()
        await session.rollback()
        stmt = (
            select(ThreadTicketSub)
            .where(ThreadTicketSub.issue_key == issue_key)
            .where(ThreadTicketSub.chat_id == message.chat_id)
        )
        result = await session.execute(stmt)
        sub = result.scalars().one_or_none()
        assert sub is None
        pachca_client.send_message.assert_not_called()
    else:
        assert False, "Exception was not raised, but it should"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/subscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_subscribe_is_transactional_with_broken_pachca(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    patcher = patch("app.service.pachca_client.PachcaClient.send_message")
    method = patcher.start()
    method.side_effect = Exception()
    try:
        await process_subscribe(
            message=message,
            tracker_queue_key=tracker_queue_key,
            session=session,
            pachca_client=pachca_client,
        )
    except Exception:
        patcher.stop()
        await session.rollback()
        stmt = (
            select(ThreadTicketSub)
            .where(ThreadTicketSub.issue_key == issue_key)
            .where(ThreadTicketSub.chat_id == message.chat_id)
        )
        result = await session.execute(stmt)
        sub = result.scalars().one_or_none()
        assert sub is None
        method.assert_called_once()
    else:
        assert False, "Exception was not raised, but it should"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/unsubscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_unsubscribe_is_transactional_with_broken_orm(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    sub = ThreadTicketSub(
        issue_key=issue_key,
        chat_id=message.chat_id,
        message_id=message.id,
    )
    session.add(sub)
    await session.commit()
    patcher = patch("sqlalchemy.ext.asyncio.AsyncSession.delete")
    patcher.start().side_effect = Exception()
    try:
        await process_unsubscribe(
            message=message,
            tracker_queue_key=tracker_queue_key,
            session=session,
            pachca_client=pachca_client,
        )
    except Exception:
        patcher.stop()
        await session.rollback()
        stmt = (
            select(ThreadTicketSub)
            .where(ThreadTicketSub.issue_key == issue_key)
            .where(ThreadTicketSub.chat_id == message.chat_id)
        )
        result = await session.execute(stmt)
        sub = result.scalars().one()
        assert sub.issue_key == issue_key
        assert sub.chat_id == message.chat_id
        assert sub.message_id == message.id
        pachca_client.send_message.assert_not_called()
    else:
        assert False, "Exception was not raised, but it should"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tracker_queue_key", "issue_key", "message"),
    (
        (
            "BACKLOG",
            "BACKLOG-1",
            pachca_message_factory(
                id=1,
                chat_id=1,
                content="/unsubscribe BACKLOG-1",
            ),
        ),
    ),
)
async def test_process_unsubscribe_is_transactional_with_broken_pachca(
    issue_key: str,
    message: PachcaMessage,
    tracker_queue_key: str,
    session: AsyncSession,
    pachca_client: PachcaClient,
):
    sub = ThreadTicketSub(
        issue_key=issue_key,
        chat_id=message.chat_id,
        message_id=message.id,
    )
    session.add(sub)
    await session.commit()
    patcher = patch("app.service.pachca_client.PachcaClient.send_message")
    method = patcher.start()
    method.side_effect = Exception()
    try:
        await process_unsubscribe(
            message=message,
            tracker_queue_key=tracker_queue_key,
            session=session,
            pachca_client=pachca_client,
        )
    except Exception:
        patcher.stop()
        await session.rollback()
        stmt = (
            select(ThreadTicketSub)
            .where(ThreadTicketSub.issue_key == issue_key)
            .where(ThreadTicketSub.chat_id == message.chat_id)
        )
        result = await session.execute(stmt)
        sub = result.scalars().one()
        assert sub.issue_key == issue_key
        assert sub.chat_id == message.chat_id
        assert sub.message_id == message.id
        method.assert_called_once()
    else:
        assert False, "Exception was not raised, but it should"
