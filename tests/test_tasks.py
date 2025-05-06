from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import call

from app.config import AppConfig
from app.service.orm.models import StudentMessage
from app.service.tasks.response_sla_notification import notify_about_pending_questions
from app.service.telegram_client import TelegramClient


@pytest.mark.asyncio
async def test_notify_about_pending_questions_no_messages(
    session: AsyncSession,
    telegram_client: TelegramClient,
    app_config: AppConfig,
):
    await notify_about_pending_questions(
        session=session,
        telegram_client=telegram_client,
        config=app_config,
    )
    telegram_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_about_pending_questions_not_violated_sla(
    session: AsyncSession,
    telegram_client: TelegramClient,
    app_config: AppConfig,
):
    test_time = datetime(1970, 1, 1, 7, 0, 0, tzinfo=timezone.utc)
    session.add_all(
        (
            StudentMessage(
                message_id=1,
                message_group_id=1,
                user_id=1,
                chat_id=1,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time,
            ),
            StudentMessage(
                message_id=3,
                message_group_id=1,
                user_id=1,
                chat_id=1,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time,
            ),
            StudentMessage(
                message_id=4,
                message_group_id=2,
                user_id=2,
                chat_id=2,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello2",
                received_reaction=False,
                sent_at=test_time,
            ),
        )
    )
    await session.commit()
    await notify_about_pending_questions(
        session=session,
        telegram_client=telegram_client,
        config=app_config,
        check_time=test_time + timedelta(seconds=app_config.response_sla_seconds - 1),
    )
    telegram_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_about_pending_questions_violated_sla(
    session: AsyncSession,
    telegram_client: TelegramClient,
    app_config: AppConfig,
):
    test_time = datetime(1970, 1, 1, 7, 0, 0, tzinfo=timezone.utc)
    session.add(
        StudentMessage(
            message_id=1,
            message_group_id=1,
            user_id=1,
            chat_id=1,
            thread_message_id=None,
            thread_chat_id=None,
            text="hello",
            received_reaction=False,
            sent_at=test_time,
            course="HardDE",
        )
    )
    await session.commit()
    await notify_about_pending_questions(
        session=session,
        telegram_client=telegram_client,
        config=app_config,
        check_time=test_time + timedelta(seconds=app_config.response_sla_seconds + 1),
    )
    telegram_client.send_message.assert_awaited_once_with(
        chat_id=app_config.telegram_chat_id,
        message=(
            "#HardDE: сообщения ожидающие реакции:\n\n"
            "https://app.pachca.com/chats/1?message=1"
        )
    )


@pytest.mark.asyncio
async def test_notify_about_pending_questions_violated_sla_multiple(
    session: AsyncSession,
    telegram_client: TelegramClient,
    app_config: AppConfig,
):
    test_time = datetime(2025, 5, 7, 7, 0, 0, tzinfo=timezone.utc)
    session.add_all(
        (
            StudentMessage(
                message_id=1,
                message_group_id=1,
                user_id=1,
                chat_id=1,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time,
                course="HardDE",
            ),
            StudentMessage(
                message_id=2,
                message_group_id=1,
                user_id=1,
                chat_id=1,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time + timedelta(seconds=app_config.response_sla_seconds),
                course="HardDE",
            ),
            StudentMessage(
                message_id=3,
                message_group_id=2,
                user_id=2,
                chat_id=1,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time,
                course="HardDE",
            ),
            StudentMessage(
                message_id=4,
                message_group_id=3,
                user_id=3,
                chat_id=2,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time + timedelta(seconds=app_config.response_sla_seconds),
                course="HardDE",
            ),
            StudentMessage(
                message_id=5,
                message_group_id=4,
                user_id=4,
                chat_id=3,
                thread_message_id=None,
                thread_chat_id=None,
                text="hello",
                received_reaction=False,
                sent_at=test_time,
                course="StartDE",
            ),
        )
    )
    await session.commit()
    await notify_about_pending_questions(
        session=session,
        telegram_client=telegram_client,
        config=app_config,
        check_time=test_time + timedelta(seconds=app_config.response_sla_seconds + 1),
    )
    telegram_client.send_message.assert_has_awaits(
        (
            call(
                chat_id=app_config.telegram_chat_id,
                message=(
                    "#HardDE: сообщения ожидающие реакции:\n\n"
                    "https://app.pachca.com/chats/1?message=1\n\n"
                    "https://app.pachca.com/chats/1?message=3"
                )
            ),
            call(
                chat_id=app_config.telegram_chat_id,
                message=(
                    "#StartDE: сообщения ожидающие реакции:\n\n"
                    "https://app.pachca.com/chats/3?message=5"
                )
            ),   
        )
    )
