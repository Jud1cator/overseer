import logging
from datetime import datetime, timezone

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


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


class PachcaClient:
    HOST = "https://api.pachca.com/api/shared/v1"

    def __init__(self, token: str):
        self._token = token

    def _get_headers(self):
        return {"Authorization": f"Bearer {self._token}"}

    def get_chats(self):
        response = requests.get(
            url=f"{self.HOST}/chats",
            headers=self._get_headers(),
        )
        if response.status_code != 200:
            logger.error(response.content)
            response.raise_for_status()
        return response.json()

    def get_messages(
        self,
        chat_id: int,
        sent_after: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc),
        per_page: int = 50,
    ) -> list[Message]:
        page = 1
        messages = []
        while True:
            response = requests.get(
                url=f"{self.HOST}/messages",
                headers=self._get_headers(),
                params={"chat_id": chat_id, "per": per_page, "page": page},
            )
            if response.status_code != 200:
                logger.error(response.content)
                response.raise_for_status()
            raw_messages = response.json()["data"]
            for raw_message in raw_messages:
                message = Message(**raw_message)
                if message.created_at >= sent_after:
                    messages.append(message)
                else:
                    return messages
            if len(raw_messages) < per_page:
                return messages
            else:
                page += 1

    def send_message(
        self,
        chat_id: int,
        text: str,
        parent_message_id: int | None = None,
    ):
        body = {
            "message": {
                "entity_id": chat_id,
                "content": text,
            }
        }
        if parent_message_id is not None:
            body["message"]["parent_message_id"] = parent_message_id
        response = requests.post(
            url=f"{self.HOST}/messages",
            headers=self._get_headers(),
            json=body,
        )
        if response.status_code != 200:
            logger.error(response.content.decode())
            response.raise_for_status()
        else:
            logger.info(f"Message {response['data']['id']} successfuly sent")
