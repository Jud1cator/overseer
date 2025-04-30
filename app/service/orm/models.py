from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    type_annotation_map = {
        datetime: TIMESTAMP(timezone=True),
    }


class ThreadTicketSub(Base):
    __tablename__ = "thread_ticket_sub"

    issue_key: Mapped[str] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))


class StudentMessage(Base):
    __tablename__ = "student_message"

    message_id: Mapped[int] = mapped_column(primary_key=True)
    message_group_id: Mapped[int] = mapped_column(BigInteger())
    user_id: Mapped[int]
    chat_id: Mapped[int]
    thread_message_id: Mapped[int | None] = mapped_column(default=None)
    thread_chat_id: Mapped[int | None] = mapped_column(default=None)
    text: Mapped[str]
    received_reaction: Mapped[bool] = mapped_column(default=False)
    received_reaction_at: Mapped[datetime | None] = mapped_column(default=None)
    reaction_message_id: Mapped[int | None] = mapped_column(default=None)
    sent_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
