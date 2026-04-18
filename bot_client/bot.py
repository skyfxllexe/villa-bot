import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot_client.handlers import start
from database.connection import init_db
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_CLIENT_TOKEN")

async def main():
    bot = Bot(token=TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)

    print("🤖 Бот клиентов запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())