import re
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import PachcaMessage, PachcaReaction
from app.config import AppConfig
from app.service.orm.models import StudentMessage, ThreadTicketSub
from app.service.pachca_client import PachcaClient
from app.service.pachca_client.models import User


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
    stmt = (
        select(ThreadTicketSub)
        .where(ThreadTicketSub.issue_key == issue_key)
        .where(ThreadTicketSub.chat_id == message.chat_id)
    )
    result = (await session.execute(stmt)).scalar_one_or_none()
    if result is None:
        sub = ThreadTicketSub(
            issue_key=issue_key,
            chat_id=message.chat_id,
            message_id=message.id,
        )
        session.add(sub)
        await pachca_client.send_message(
            chat_id=message.chat_id,
            text=f"Я сообщу вам об изменении статуса тикета {issue_key}",
            parent_message_id=message.id,
        )
        await session.commit()
    else:
        await pachca_client.send_message(
            chat_id=message.chat_id,
            text=f"Тикет {issue_key} уже отслеживается в этом треде",
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
    result = (await session.execute(stmt)).scalar_one_or_none()
    if result is None:
        await pachca_client.send_message(
            chat_id=message.chat_id,
            text=f"Тикет {issue_key} не отслеживался в этом треде",
            parent_message_id=message.id,
        )
    else:
        await session.delete(result)
        await pachca_client.send_message(
            chat_id=message.chat_id,
            text=f"Тикет {issue_key} больше не отслеживается в этом треде",
            parent_message_id=message.id,
        )
        await session.commit()


def user_is_expert(user: User) -> bool:
    return any(t in {"expert_HardDE", "expert_StartDE"} for t in user.list_tags)


def user_is_student(user: User) -> bool:
    return any(re.match(r"HardDE_\d+|StartDE_\d+", t) is not None for t in user.list_tags)


async def react_to_message_group(
    session: AsyncSession,
    student_message: StudentMessage,
    received_reaction_at: datetime,
    reaction_message_id: int | None = None,
) -> None:
    stmt = select(StudentMessage).where(StudentMessage.message_group_id == student_message.message_group_id)
    results = (await session.execute(stmt)).scalars().all()
    for r in results:
        r.received_reaction = True
        r.received_reaction_at = received_reaction_at
        r.reaction_message_id = reaction_message_id
        session.add(r)


async def process_student_mesage(
    message: PachcaMessage,
    config: AppConfig,
    session: AsyncSession,
) -> None:
    stmt = (
        select(StudentMessage)
        .where(~StudentMessage.received_reaction)
        .where(StudentMessage.user_id == message.user_id)
        .where(
            (StudentMessage.chat_id == message.chat_id)
            | (StudentMessage.message_id == message.thread.message_id if message.thread is not None else False)
        )
        .where(
            message.created_at - StudentMessage.sent_at <= timedelta(seconds=config.message_group_time_frame_seconds)
        )
    )
    results = (await session.execute(stmt)).scalars().all()
    if len(results) == 0:
        message_group_id = hash((message.user_id, message.chat_id, message.created_at))
        logger.info(f"Received message {message.id} from new message group: {message_group_id}")
    else:
        message_group_id = results[0].message_group_id
        logger.info(f"Received message {message.id} from existing message group: {message_group_id}")
    new_msg = StudentMessage(
        message_id=message.id,
        message_group_id=message_group_id,
        user_id=message.user_id,
        chat_id=message.chat_id,
        thread_message_id=message.thread.message_id if message.thread is not None else None,
        thread_chat_id=message.thread.message_chat_id if message.thread is not None else None,
        text=message.content,
        received_reaction=False,
        sent_at=message.created_at,
    )
    session.add(new_msg)
    await session.commit()


async def process_expert_message(message: PachcaMessage, config: AppConfig, session: AsyncSession) -> None:
    if message.parent_message_id is None:
        logger.info(f"Message {message.id} is from an expert but is not a reply, skipping")
        return
    stmt = (
        select(StudentMessage)
        .where(~StudentMessage.received_reaction)
        .where(StudentMessage.message_id == message.parent_message_id)
    )
    result = (await session.execute(stmt)).scalar_one_or_none()
    if result is None:
        logger.info(
            f"Message {message.id} is a reply to message {message.parent_message_id}"
            " which is not a pending student question, skipping"
        )
        return
    # If we are here, it means reply to some message from pending message group is received
    # We may mark all messages from that group as reacted to
    await react_to_message_group(
        session=session,
        student_message=result,
        received_reaction_at=message.created_at,
        reaction_message_id=message.id,
    )
    await session.commit()


async def process_message(
    message: PachcaMessage,
    config: AppConfig,
    session: AsyncSession,
    pachca_client: PachcaClient,
) -> None:
    user = await pachca_client.get_user(message.user_id)
    if user_is_student(user):
        await process_student_mesage(message, config, session)
    elif user_is_expert(user):
        await process_expert_message(message, config, session)
    else:
        logger.info(f"Message {message.id} is ignored because it is not from student or expert")


async def process_reaction(
    reaction: PachcaReaction,
    session: AsyncSession,
    pachca_client: PachcaClient,
) -> None:
    if reaction.event != "new":
        logger.info("Reaction deletions are skipped")
        return
    user = await pachca_client.get_user(reaction.user_id)
    if not user_is_expert(user):
        logger.info("Reactions not from experts are skipped")
        return
    stmt = (
        select(StudentMessage)
        .where(~StudentMessage.received_reaction)
        .where(StudentMessage.message_id == reaction.message_id)
    )
    result = (await session.execute(stmt)).scalar_one_or_none()
    if result is None:
        logger.info(f"Reacted message {reaction.message_id} was not tracked as pending student message")
        return
    await react_to_message_group(
        session=session,
        student_message=result,
        received_reaction_at=reaction.created_at,
    )
    await session.commit()
