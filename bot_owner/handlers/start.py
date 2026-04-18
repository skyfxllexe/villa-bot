from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from bot_owner.keyboards.menus import main_menu
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton



from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import InviteCode, Owner
from datetime import datetime

router = Router()

class AuthForm(StatesGroup):
    waiting_code = State()

# ─── /start ───────────────────────────────────────
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    # Проверяем — уже авторизован?
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Owner).where(Owner.telegram_id == message.from_user.id)
        )
        owner = result.scalar_one_or_none()

    if owner and owner.is_active:
        # Уже авторизован — показываем меню
        await show_owner_menu(message)
    else:
        # Не авторизован — просим код
        # Проверяем инвайт в ссылке (/start КОД)
        args = message.text.split()
        if len(args) > 1:
            await try_activate_code(message, state, args[1])
        else:
            await state.set_state(AuthForm.waiting_code)
            await message.answer(
                "👋 Привет!\n\n"
                "Это бот для хозяев вилл на Бали 🌴\n\n"
                "🔑 Введи инвайт-код для доступа:"
            )

# ─── Ввод кода вручную ────────────────────────────
@router.message(AuthForm.waiting_code)
async def check_code(message: Message, state: FSMContext):
    await try_activate_code(message, state, message.text.strip())

# ─── Проверка и активация кода ────────────────────
async def try_activate_code(message: Message, state: FSMContext, code: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(InviteCode).where(InviteCode.code == code.upper())
        )
        invite = result.scalar_one_or_none()

        # Проверки
        if not invite:
            await message.answer("❌ Неверный код. Попробуй ещё раз:")
            return

        if invite.is_used:
            await message.answer("❌ Этот код уже использован.")
            await state.clear()
            return

        if invite.expires_at and invite.expires_at < datetime.utcnow():
            await message.answer("❌ Срок действия кода истёк. Запросите новый.")
            await state.clear()
            return

        # Всё ок — создаём хозяина
        owner = Owner(
            telegram_id = message.from_user.id,
            username    = message.from_user.username,
            first_name  = message.from_user.first_name,
        )
        db.add(owner)
        await db.flush()

        # Помечаем код как использованный
        invite.is_used  = True
        invite.owner_id = owner.id
        invite.used_at  = datetime.utcnow()

        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ *Добро пожаловать, {message.from_user.first_name}!*\n\n"
        "Теперь у тебя есть доступ к боту 🎉",
        parse_mode="Markdown"
    )
    await show_owner_menu(message)

# ─── Меню хозяина ─────────────────────────────────
async def show_owner_menu(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Добавить виллу")],
            [KeyboardButton(text="📋 Мои виллы")],
            [KeyboardButton(text="📊 Статистика броней")],
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"🌴 *Панель хозяина*\n\n"
        f"Привет, хозяин!\n"
        "Что хочешь сделать?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

