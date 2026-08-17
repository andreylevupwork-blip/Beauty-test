import asyncio

from aiogram import Bot

from config import settings


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    try:
        me = await bot.get_me()
        print(f"OK: token valid. Bot username: @{me.username}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

