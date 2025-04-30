import os
from typing import AsyncGenerator

from aiogram import Bot


class TelegramClient:
    def __init__(self, token: str):
        self.bot = Bot(token=token)

    async def send_message(self, chat_id: int, message: str) -> None:
        await self.bot.send_message(chat_id=chat_id, text=message)


async def get_client() -> AsyncGenerator[TelegramClient, None]:
    yield TelegramClient(token=os.environ["TELEGRAM_TOKEN"])
