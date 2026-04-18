
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot_owner.handlers import start, add_villa, my_villas, admin
from database.connection import init_db  

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_OWNER_TOKEN")

async def main():
    # await init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем все роутеры
    dp.include_router(start.router)
    dp.include_router(add_villa.router)
    dp.include_router(my_villas.router)
    dp.include_router(admin.router)
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())