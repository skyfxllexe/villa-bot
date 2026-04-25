from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Booking, Villa
import json

router = Router()

def booking_status(status: str) -> str:
    return {
        "pending":   "⏳ Ожидает подтверждения",
        "confirmed": "✅ Подтверждена",
        "cancelled": "❌ Отменена",
        "completed": "🏁 Завершена",
    }.get(status, status)

# ─── Мои брони ────────────────────────────────────
@router.message(F.text == "📋 Мои брони")
async def my_bookings(message: Message):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.client_tg_id == message.from_user.id
            ).order_by(Booking.created_at.desc())
        )
        bookings = result.scalars().all()

    if not bookings:
        await message.answer(
            "📋 У тебя пока нет броней.\n\n"
            "Найди виллу в каталоге и забронируй! 🌴"
        )
        return

    await message.answer(
        f"📋 *Мои брони ({len(bookings)}):*\n\n"
        "Нажми на бронь для подробностей:",
        parse_mode="Markdown",
        reply_markup=bookings_list_keyboard(bookings)
    )

def bookings_list_keyboard(bookings: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bookings:
        status_icon = {
            "pending":   "⏳",
            "confirmed": "✅",
            "cancelled": "❌",
            "completed": "🏁",
        }.get(b.status, "❓")

        buttons.append([InlineKeyboardButton(
            text=f"{status_icon} {b.checkin.strftime('%d.%m')} → {b.checkout.strftime('%d.%m.%Y')}",
            callback_data=f"my_booking_{b.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── Детали брони ─────────────────────────────────
@router.callback_query(F.data.startswith("my_booking_"))
async def view_my_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

        if not booking:
            await callback.answer("❌ Бронь не найдена")
            return

        villa_result = await db.execute(
            select(Villa).where(Villa.id == booking.villa_id)
        )
        villa = villa_result.scalar_one_or_none()

    nights = (booking.checkout - booking.checkin).days

    text = (
        f"📋 *Детали брони*\n\n"
        f"🏠 Вилла: {villa.name if villa else '—'}\n"
        f"📍 {villa.location if villa else '—'}\n"
        f"📅 Заезд: {booking.checkin.strftime('%d.%m.%Y')}\n"
        f"📅 Выезд: {booking.checkout.strftime('%d.%m.%Y')}\n"
        f"🌙 Ночей: {nights}\n\n"
        f"Статус: {booking_status(booking.status)}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_bookings")],
    ])

    # Если бронь ожидает — можно отменить
    if booking.status == "pending":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"client_cancel_{booking_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_bookings")],
        ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# ─── Отмена брони клиентом ────────────────────────
@router.callback_query(F.data.startswith("client_cancel_"))
async def client_cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])

    await callback.message.edit_text(
        "❌ *Отменить бронь?*\n\nЭто действие необратимо.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"client_confirm_cancel_{booking_id}"),
                InlineKeyboardButton(text="◀️ Нет",          callback_data=f"my_booking_{booking_id}"),
            ]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("client_confirm_cancel_"))
async def client_confirm_cancel(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[3])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

        if not booking or booking.status != "pending":
            await callback.answer("❌ Невозможно отменить", show_alert=True)
            return

        booking.status = "cancelled"
        await db.commit()

    await callback.message.edit_text("✅ Бронь отменена!")
    await callback.answer()

# ─── Назад к списку ───────────────────────────────
@router.callback_query(F.data == "back_to_bookings")
async def back_to_bookings(callback: CallbackQuery):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.client_tg_id == callback.from_user.id
            ).order_by(Booking.created_at.desc())
        )
        bookings = result.scalars().all()

    await callback.message.edit_text(
        f"📋 *Мои брони ({len(bookings)}):*\n\nНажми на бронь для подробностей:",
        reply_markup=bookings_list_keyboard(bookings),
        parse_mode="Markdown"
    )
    await callback.answer()