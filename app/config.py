from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class AppConfig(BaseSettings):
    pachca_token: str
    telegram_token: str
    telegram_chat_id: int
    tracker_queue_key: str = "BACKLOG"
    tracker_status_list: set[str] = set(["Закрыт"])
    message_group_time_frame_seconds: int = 1 * 60 * 60  # 1h
    response_sla_seconds: int = 55 * 60  # 55 min
    response_sla_notifications_period_seconds: int = 10 * 60  # 10 min


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()  # type: ignore
