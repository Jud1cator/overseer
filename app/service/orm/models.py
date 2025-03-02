from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class ThreadTicketSub(Base):
    __tablename__ = "thread_ticket_sub"

    issue_key: Mapped[str] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
