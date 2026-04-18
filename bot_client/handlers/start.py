from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

router = Router()

WEBAPP_URL = "https://skyfxllexe.github.io/villa-webapp/"

@router.message(CommandStart())
async def start_handler(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🌴 Смотреть виллы",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )],
            [KeyboardButton(text="📅 Мои брони")],
            [KeyboardButton(text="🆘 Поддержка")],
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"🌴 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в *Bali Villa Rent*!\n\n"
        "Здесь ты можешь найти и забронировать виллу на Бали 🏝",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )