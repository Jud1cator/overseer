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


class User(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    nickname: str | None
    email: str | None
    phone_number: str | None
    department: str | None
    title: str | None
    role: str | None
    suspended: bool
    invite_status: str | None
    list_tags: list[str]
    bot: bool
    created_at: str
    last_activity_at: str | None
    time_zone: str | None
    image_url: str | None
