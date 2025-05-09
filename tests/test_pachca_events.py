import typing as tp
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import PachcaMessage, PachcaReaction, ThreadInfo
from app.config import AppConfig
from app.service.event_processing.pachca_events import (
    process_message,
    process_reaction,
    process_subscribe,
    process_unsubscribe,
)
from app.service.orm.models import StudentMessage, ThreadTicketSub
from app.service.pachca_client import PachcaClient
from app.service.pachca_client.models import User as PachcaUser


def pachca_message_factory(
    id=1,
    type="message",
    event="new",
    entity_type="discussion",
    entity_id=1,
    content="default_content",
    user_id=1,
    created_at=datetime.now(timezone.utc),
    chat_id=1,
    parent_message_id=None,
    thread=None,
) -> PachcaMessage:
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


def pachca_user_factory(
    id=1,
    first_name="default_first_name",
    last_name="default_last_name",
    nickname="default_nickname",
    email="default_email",
    phone_number="default_phone_number",
    department="default_department",
    title="default_title",
    role="default_role",
    suspended=False,
    invite_status="default_invite_status",
    list_tags=("tag1",),
    bot=False,
    created_at=datetime.now(timezone.utc).isoformat(),
    last_activity_at=datetime.now(timezone.utc).isoformat(),
    time_zone="MSK",
    image_url="default_image_url",
) -> PachcaUser:
    return PachcaUser(
        id=id,
        first_name=first_name,
        last_name=last_name,
        nickname=nickname,
        email=email,
        phone_number=phone_number,
        department=department,
        title=title,
        role=role,
        suspended=suspended,
        invite_status=invite_status,
        list_tags=list_tags,
        bot=bot,
        created_at=created_at,
        last_activity_at=last_activity_at,
        time_zone=time_zone,
        image_url=image_url,
    )


def pachca_reaction_factory(
    type="reaction",
    event="new",
    message_id=1,
    code="default_code",
    user_id=1,
    created_at=datetime.now(timezone.utc),
    webhook_timestamp=datetime.now(timezone.utc),
) -> PachcaReaction:
    return PachcaReaction(
        type=type,
        event=event,
        message_id=message_id,
        code=code,
        user_id=user_id,
        created_at=created_at,
        webhook_timestamp=webhook_timestamp,
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
    sub = result.scalar_one()
    assert sub.issue_key == issue_key
    assert sub.chat_id == message.chat_id
    assert sub.message_id == message.id
    pachca_client.send_message.assert_awaited_with(
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
    pachca_client.send_message.assert_awaited_with(
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
    pachca_client.send_message.assert_awaited_with(
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
    pachca_client.send_message.assert_awaited_with(
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
        sub = result.scalar_one_or_none()
        assert sub is None
        pachca_client.send_message.assert_not_awaited()
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
        sub = result.scalar_one_or_none()
        assert sub is None
        method.assert_awaited_once()
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
        sub = result.scalar_one()
        assert sub.issue_key == issue_key
        assert sub.chat_id == message.chat_id
        assert sub.message_id == message.id
        pachca_client.send_message.assert_not_awaited()
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
        sub = result.scalar_one()
        assert sub.issue_key == issue_key
        assert sub.chat_id == message.chat_id
        assert sub.message_id == message.id
        method.assert_awaited_once()
    else:
        assert False, "Exception was not raised, but it should"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "message",
        "user",
    ),
    (
        (
            pachca_message_factory(
                id=1,
                chat_id=1,
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("StartDE_1",),
            ),
        ),
        (
            pachca_message_factory(
                id=1,
                chat_id=1,
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("HardDE_1",),
            ),
        ),
        (
            pachca_message_factory(
                id=2,
                chat_id=2,
                user_id=1,
                thread=ThreadInfo(
                    message_id=1,
                    message_chat_id=1,
                ),
            ),
            pachca_user_factory(
                id=1,
                list_tags=("StartDE_1",),
            ),
        ),
    ),
)
async def test_process_student_message(
    session: AsyncSession,
    pachca_client: PachcaClient,
    app_config: AppConfig,
    message: PachcaMessage,
    user: PachcaUser,
):
    with patch("app.service.pachca_client.PachcaClient.get_user", return_value=user):
        await process_message(message, app_config, session, pachca_client)
    stmt = select(StudentMessage).where(StudentMessage.message_id == message.id)
    result = (await session.execute(stmt)).scalar_one()
    assert not result.received_reaction


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "messages",
        "delete_event",
        "user",
    ),
    (
        (
            tuple(),
            pachca_message_factory(
                id=1,
                event="delete",
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("StartDE_1",),
            ),
        ),
        (
            (
                pachca_message_factory(
                    id=1,
                    event="new",
                    user_id=1,
                ),
            ),
            pachca_message_factory(
                id=1,
                event="delete",
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("StartDE_1",),
            ),
        ),
    ),
)
async def test_process_deleted_student_message(
    session: AsyncSession,
    pachca_client: PachcaClient,
    app_config: AppConfig,
    messages: tp.Sequence[PachcaMessage],
    delete_event: PachcaMessage,
    user: PachcaUser,
):
    with patch("app.service.pachca_client.PachcaClient.get_user", return_value=user):
        for msg in messages:
            await process_message(msg, app_config, session, pachca_client)
        await process_message(delete_event, app_config, session, pachca_client)
    stmt = select(StudentMessage).where(StudentMessage.message_id == delete_event.id)
    result = (await session.execute(stmt)).scalar_one_or_none()
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "message",
        "user",
    ),
    (
        (
            pachca_message_factory(
                id=1,
                chat_id=1,
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=tuple(),
            ),
        ),
        (
            pachca_message_factory(
                id=1,
                chat_id=1,
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("curator_StartDE",),
            ),
        ),
        (
            pachca_message_factory(
                id=1,
                chat_id=1,
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("expert_StartDE",),
            ),
        ),
    ),
)
async def test_process_other_message(
    session: AsyncSession,
    pachca_client: PachcaClient,
    app_config: AppConfig,
    message: PachcaMessage,
    user: PachcaUser,
):
    with patch("app.service.pachca_client.PachcaClient.get_user", return_value=user):
        await process_message(message, app_config, session, pachca_client)
    stmt = select(StudentMessage).where(StudentMessage.message_id == message.id)
    result = (await session.execute(stmt)).scalar_one_or_none()
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "reaction",
        "user",
    ),
    (
        (
            pachca_reaction_factory(
                message_id=1,
                user_id=1,
            ),
            pachca_user_factory(
                id=1,
                list_tags=("expert_StartDE",),
            ),
        ),
    ),
)
async def test_process_reaction_to_student_message(
    session: AsyncSession,
    pachca_client: PachcaClient,
    reaction: PachcaReaction,
    user: PachcaUser,
):
    message_group_id = 1
    message1 = StudentMessage(
        message_id=reaction.message_id - 1,
        message_group_id=message_group_id,
        user_id=69,
        chat_id=228,
        thread_message_id=322,
        thread_chat_id=1488,
        text="niggers",
        sent_at=datetime.now(timezone.utc),
    )
    message2 = StudentMessage(
        message_id=reaction.message_id,
        message_group_id=message_group_id,
        user_id=69,
        chat_id=228,
        thread_message_id=322,
        thread_chat_id=1488,
        text="niggers",
        sent_at=datetime.now(timezone.utc),
    )
    session.add(message1)
    session.add(message2)
    await session.commit()
    with patch("app.service.pachca_client.PachcaClient.get_user", return_value=user):
        await process_reaction(reaction, session, pachca_client)
    stmt = select(StudentMessage).where(StudentMessage.message_group_id == message_group_id)
    result = (await session.execute(stmt)).scalars().all()
    for r in result:
        assert r.received_reaction
