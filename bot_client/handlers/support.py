from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Booking, Villa, Owner
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

router = Router()

BOT_OWNER_TOKEN  = os.getenv("BOT_OWNER_TOKEN")
MANAGER_USERNAME = "@менеджер"

class SupportForm(StatesGroup):
    waiting_custom_message = State()

# ─── Клавиатуры ───────────────────────────────────
def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Уборка",            callback_data="ticket_cleaning")],
        [InlineKeyboardButton(text="🔥 Закончился газ",    callback_data="ticket_gas")],
        [InlineKeyboardButton(text="🏊 Почистить бассейн", callback_data="ticket_pool")],
        [InlineKeyboardButton(text="🔧 Что-то сломалось",  callback_data="ticket_repair")],
        [InlineKeyboardButton(text="💬 Другое",             callback_data="ticket_custom")],
    ])

def owner_ticket_keyboard(client_tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принял, еду",         callback_data=f"ticket_accept_{client_tg_id}")],
        [InlineKeyboardButton(text="⏰ Буду через 30 минут", callback_data=f"ticket_30min_{client_tg_id}")],
        [InlineKeyboardButton(text="⏰ Буду через 1 час",    callback_data=f"ticket_1hour_{client_tg_id}")],
        [InlineKeyboardButton(text="📞 Свяжусь с тобой",    callback_data=f"ticket_call_{client_tg_id}")],
    ])

TICKET_TEXTS = {
    "ticket_cleaning": ("🧹 Уборка",          "просит уборку"),
    "ticket_gas":      ("🔥 Закончился газ",   "сообщает что закончился газ"),
    "ticket_pool":     ("🏊 Чистка бассейна",  "просит почистить бассейн"),
    "ticket_repair":   ("🔧 Что-то сломалось", "сообщает о поломке"),
}

# ─── Кнопка Тикеты (обычная) ──────────────────────
@router.message(F.text == "🎫 Тикеты")
async def tickets_handler(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.client_tg_id == message.from_user.id,
                Booking.status       == "confirmed"
            ).order_by(Booking.checkin.desc())
        )
        bookings = result.scalars().all()

    if not bookings:
        await message.answer(
            "🎫 *Тикеты*\n\n"
            "У тебя нет подтверждённых броней.\n\n"
            "Для других вопросов нажми *🆘 Поддержка*",
            parse_mode="Markdown"
        )
        return

    # Если одна бронь — сразу открываем
    if len(bookings) == 1:
        villa_id = bookings[0].villa_id
        await state.update_data(ticket_villa_id=villa_id)

        async with AsyncSessionLocal() as db:
            villa_result = await db.execute(
                select(Villa).where(Villa.id == villa_id)
            )
            villa = villa_result.scalar_one_or_none()

        await message.answer(
            f"🎫 *Тикеты*\n\n"
            f"🏠 Вилла: {villa.name if villa else '—'}\n\n"
            "Выбери тип запроса — хозяин получит уведомление 👇",
            reply_markup=support_keyboard(),
            parse_mode="Markdown"
        )
        return

    # Если несколько броней — показываем список для выбора
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text          = f"🏠 {b.villa_id}",
            callback_data = f"open_tickets_{b.villa_id}"
        )]
        for b in bookings
    ])

    await message.answer(
        "🎫 *Тикеты*\n\nВыбери виллу:",
        reply_markup = keyboard,
        parse_mode   = "Markdown"
    )
# ─── Кнопка тикетов из подтверждения брони ────────
@router.callback_query(F.data.startswith("open_tickets_"))
async def open_tickets(callback: CallbackQuery, state: FSMContext):
    villa_id = int(callback.data.split("_")[2])

    # Проверяем что у клиента есть подтверждённая бронь на эту виллу
    async with AsyncSessionLocal() as db:
        booking_result = await db.execute(
            select(Booking).where(
                Booking.client_tg_id == callback.from_user.id,
                Booking.villa_id     == villa_id,
                Booking.status       == "confirmed"
            )
        )
        booking = booking_result.scalar_one_or_none()

        if not booking:
            await callback.answer(
                "❌ У тебя нет активной брони на эту виллу",
                show_alert=True
            )
            return

        villa_result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = villa_result.scalar_one_or_none()

    await state.update_data(ticket_villa_id=villa_id)

    await callback.message.answer(
        f"🎫 *Тикеты*\n\n"
        f"🏠 Вилла: {villa.name if villa else '—'}\n\n"
        "Выбери тип запроса — хозяин получит уведомление 👇",
        reply_markup=support_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Быстрые тикеты ───────────────────────────────
@router.callback_query(F.data.in_({
    "ticket_cleaning", "ticket_gas",
    "ticket_pool",     "ticket_repair"
}))
async def send_quick_ticket(callback: CallbackQuery, state: FSMContext):
    ticket_type        = callback.data
    title, description = TICKET_TEXTS[ticket_type]

    # Берём villa_id из state
    data     = await state.get_data()
    villa_id = data.get("ticket_villa_id")

    if not villa_id:
        await callback.answer("❌ Открой тикеты через кнопку в подтверждении брони", show_alert=True)
        return

    async with AsyncSessionLocal() as db:
        villa_result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = villa_result.scalar_one_or_none()

        if not villa:
            await callback.answer("❌ Вилла не найдена", show_alert=True)
            return

        owner_result = await db.execute(
            select(Owner).where(Owner.id == villa.owner_id)
        )
        owner = owner_result.scalar_one_or_none()

        # Находим бронь клиента
        booking_result = await db.execute(
            select(Booking).where(
                Booking.client_tg_id == callback.from_user.id,
                Booking.villa_id     == villa_id,
                Booking.status       == "confirmed"
            )
        )
        booking = booking_result.scalar_one_or_none()

    await callback.message.edit_text(
        f"✅ *Запрос отправлен хозяину!*\n\n"
        f"{title}\n\n"
        "Хозяин скоро ответит 🙌",
        parse_mode="Markdown"
    )

    if BOT_OWNER_TOKEN and owner:
        owner_bot = Bot(token=BOT_OWNER_TOKEN)
        try:
            await owner_bot.send_message(
                chat_id      = owner.telegram_id,
                text         = (
                    f"🔔 *Запрос от жильца!*\n\n"
                    f"🏠 Вилла: {villa.name}\n"
                    f"👤 Жилец: {booking.client_name if booking else '—'}\n"
                    f"📱 Телефон: {booking.client_phone if booking else '—'}\n\n"
                    f"{title}\n"
                    f"Жилец {description}"
                ),
                reply_markup = owner_ticket_keyboard(callback.from_user.id),
                parse_mode   = "Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки тикета: {e}")
        finally:
            await owner_bot.session.close()

    await callback.answer()

# ─── Свой текст ───────────────────────────────────
@router.callback_query(F.data == "ticket_custom")
async def ticket_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportForm.waiting_custom_message)
    await callback.message.edit_text(
        "💬 Напиши своё сообщение хозяину:\n\n"
        "Опиши проблему подробно."
    )
    await callback.answer()

@router.message(SupportForm.waiting_custom_message)
async def get_custom_message(message: Message, state: FSMContext):
    data     = await state.get_data()
    villa_id = data.get("ticket_villa_id")
    await state.clear()

    if not villa_id:
        await message.answer("❌ Открой тикеты через кнопку в подтверждении брони")
        return

    async with AsyncSessionLocal() as db:
        villa_result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = villa_result.scalar_one_or_none()

        if not villa:
            await message.answer("❌ Вилла не найдена")
            return

        owner_result = await db.execute(
            select(Owner).where(Owner.id == villa.owner_id)
        )
        owner = owner_result.scalar_one_or_none()

        booking_result = await db.execute(
            select(Booking).where(
                Booking.client_tg_id == message.from_user.id,
                Booking.villa_id     == villa_id,
                Booking.status       == "confirmed"
            )
        )
        booking = booking_result.scalar_one_or_none()

    await message.answer(
        f"✅ *Сообщение отправлено хозяину!*\n\n_{message.text}_",
        parse_mode="Markdown"
    )

    if BOT_OWNER_TOKEN and owner:
        owner_bot = Bot(token=BOT_OWNER_TOKEN)
        try:
            await owner_bot.send_message(
                chat_id      = owner.telegram_id,
                text         = (
                    f"🔔 *Сообщение от жильца!*\n\n"
                    f"🏠 Вилла: {villa.name}\n"
                    f"👤 Жилец: {booking.client_name if booking else '—'}\n"
                    f"📱 Телефон: {booking.client_phone if booking else '—'}\n\n"
                    f"💬 *{message.text}*"
                ),
                reply_markup = owner_ticket_keyboard(message.from_user.id),
                parse_mode   = "Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки тикета: {e}")
        finally:
            await owner_bot.session.close()