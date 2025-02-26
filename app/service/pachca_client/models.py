from datetime import datetime

from pydantic import BaseModel


class ThreadInfo(BaseModel):
    id: int
    chat_id: int


class Message(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    chat_id: int
    content: str
    user_id: int
    created_at: datetime
    thread: ThreadInfo | None
