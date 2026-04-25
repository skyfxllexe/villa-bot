import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot_client.handlers import start, catalog, booking, my_bookings, support
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_CLIENT_TOKEN")

async def main():
    bot = Bot(token=TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(my_bookings.router)
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(booking.router)
    dp.include_router(support.router)



    print("🤖 Бот клиентов запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())