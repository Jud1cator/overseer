import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import aiohttp
from loguru import logger

from app.service.pachca_client.models import Message


class PachcaClient:
    HOST = "https://api.pachca.com/api/shared/v1"

    def __init__(self, token: str):
        self._token = token

    def _get_headers(self):
        return {"Authorization": f"Bearer {self._token}"}

    async def get_chats(self):
        response = await self._session.get(
            url=f"{self.HOST}/chats",
            headers=self._get_headers(),
        )
        if response.status != 200:
            logger.error(await response.text())
            response.raise_for_status()
        return await response.json()

    async def get_messages(
        self,
        chat_id: int,
        sent_after: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc),
        per_page: int = 50,
    ) -> list[Message]:
        page = 1
        messages = []
        while True:
            response = await self._session.get(
                url=f"{self.HOST}/messages",
                headers=self._get_headers(),
                params={"chat_id": chat_id, "per": per_page, "page": page},
            )
            if response.status != 200:
                logger.error(response.content)
                response.raise_for_status()
            raw_messages = await response.json()
            for raw_message in raw_messages["data"]:
                message = Message(**raw_message)
                if message.created_at >= sent_after:
                    messages.append(message)
                else:
                    break
            if len(raw_messages) < per_page:
                break
            else:
                page += 1
        return messages

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parent_message_id: int | None,
    ):
        body = {
            "message": {
                "entity_id": chat_id,
                "content": text,
            }
        }
        if parent_message_id is not None:
            body["message"]["parent_message_id"] = parent_message_id

            response = await self._session.post(
                url=f"{self.HOST}/messages",
                headers=self._get_headers(),
                json=body,
            )
        if response.status != 200:
            logger.error(await response.text())
            response.raise_for_status()
        else:
            json = await response.json()
            logger.info(f"Message {json['data']['id']} successfuly sent")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._session.close()


def get_client():
    return PachcaClient(token=os.environ["PACHCA_TOKEN"])
