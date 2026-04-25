from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
router = Router()
MANAGER_USERNAME = "@discxnnectedexe"  # вставишь сам


@router.message(CommandStart())
async def start_handler(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Каталог вилл")],
            [KeyboardButton(text="📋 Мои брони")],
            [KeyboardButton(text="🆘 Поддержка")],
            [KeyboardButton(text="🎫 Тикеты")], 
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
@router.message(F.text.in_(["📞 Связаться с менеджером", "🆘 Поддержка"]))
async def support(message: Message):
    await message.answer(
        f"📞 *Связаться с менеджером*\n\n"
        f"Напишите напрямую: {MANAGER_USERNAME}\n\n"
        "Мы ответим в течение часа 🙌",
        parse_mode="Markdown"
    )