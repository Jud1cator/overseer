from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP
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
