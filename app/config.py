from functools import lru_cache

from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    pachca_token: str
    tracker_queue_key: str = "BACKLOG"
    tracker_status_list: set[str] = set(["Закрыт"])


@lru_cache
def get_config():
    return AppConfig()
