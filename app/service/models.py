from datetime import datetime

from pydantic import BaseModel


class ThreadInfo(BaseModel):
    message_id: int
    message_chat_id: int


class PachcaMessage(BaseModel):
    type: str
    id: int
    event: str
    entity_type: str
    entity_id: int
    content: str
    user_id: int
    created_at: datetime
    chat_id: int
    parent_message_id: int | None
    thread: ThreadInfo | None


class TicketStatusChange(BaseModel):
    issue_key: str
    status: str
