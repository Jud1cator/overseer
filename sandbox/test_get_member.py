import asyncio
import os

from app.service.pachca_client import PachcaClient


async def main():
    async with PachcaClient(token=os.environ["PACHCA_TOKEN"]) as client:
        chat_info = await client.get_chat_info(21212429)
        for member in chat_info["data"]["member_ids"]:
            print(await client.get_user(member))


if __name__ == "__main__":
    asyncio.run(main())
