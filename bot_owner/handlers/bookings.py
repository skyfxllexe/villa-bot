from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Booking, Villa
import os
from dotenv import load_dotenv

load_dotenv()

router = Router()

BOT_CLIENT_TOKEN = os.getenv("BOT_CLIENT_TOKEN")

OWNER_RESPONSES = {
    "ticket_accept": "✅ Хозяин принял запрос и уже едет!",
    "ticket_30min":  "⏰ Хозяин будет через 30 минут.",
    "ticket_1hour":  "⏰ Хозяин будет через 1 час.",
    "ticket_call":   "📞 Хозяин скоро свяжется с тобой.",
}

# ─── Клавиатура подтверждённой брони для клиента ──
def client_confirmed_keyboard(villa_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text          = "🎫 Тикеты (запросы по вилле)",
            callback_data = f"open_tickets_{villa_id}"
        )],
    ])

# ─── Список броней ────────────────────────────────
def bookings_keyboard(bookings: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bookings:
        status = "✅" if b.status == "confirmed" else "⏳"
        buttons.append([InlineKeyboardButton(
            text=f"{status} {b.checkin.strftime('%d.%m')} → {b.checkout.strftime('%d.%m')} — {b.client_name}",
            callback_data=f"view_booking_{b.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def booking_manage_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Снять бронь", callback_data=f"cancel_booking_{booking_id}")],
        [InlineKeyboardButton(text="◀️ Назад",        callback_data="my_bookings")],
    ])

def cancel_confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, снять", callback_data=f"confirm_cancel_{booking_id}"),
            InlineKeyboardButton(text="◀️ Нет",       callback_data=f"view_booking_{booking_id}"),
        ]
    ])

# ─── Мои брони ────────────────────────────────────
@router.message(F.text == "📊 Статистика броней")
async def my_bookings(message: Message):
    from database.models import Owner

    async with AsyncSessionLocal() as db:
        owner_result = await db.execute(
            select(Owner).where(Owner.telegram_id == message.from_user.id)
        )
        owner = owner_result.scalar_one_or_none()

        if not owner:
            await message.answer("❌ Ты не авторизован!")
            return

        villas_result = await db.execute(
            select(Villa).where(Villa.owner_id == owner.id)
        )
        villas = villas_result.scalars().all()

        if not villas:
            await message.answer("🏠 У тебя пока нет вилл!")
            return

        villa_ids = [v.id for v in villas]

        bookings_result = await db.execute(
            select(Booking).where(
                Booking.villa_id.in_(villa_ids),
                Booking.status.in_(["pending", "confirmed"])
            ).order_by(Booking.checkin)
        )
        bookings = bookings_result.scalars().all()

    if not bookings:
        await message.answer("📅 Активных броней пока нет!")
        return

    villa_map = {v.id: v.name for v in villas}
    text = "📊 *Активные брони:*\n\n"
    for b in bookings:
        status = "✅ Подтверждена" if b.status == "confirmed" else "⏳ Ожидает"
        text += (
            f"🏠 {villa_map.get(b.villa_id, '—')}\n"
            f"📅 {b.checkin.strftime('%d.%m.%Y')} → {b.checkout.strftime('%d.%m.%Y')}\n"
            f"👤 {b.client_name} • {b.client_phone}\n"
            f"Статус: {status}\n\n"
        )

    await message.answer(
        text,
        reply_markup=bookings_keyboard(bookings),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "my_bookings")
async def my_bookings_callback(callback: CallbackQuery):
    from database.models import Owner

    async with AsyncSessionLocal() as db:
        owner_result = await db.execute(
            select(Owner).where(Owner.telegram_id == callback.from_user.id)
        )
        owner = owner_result.scalar_one_or_none()

        if not owner:
            await callback.answer("❌ Ты не авторизован!", show_alert=True)
            return

        villas_result = await db.execute(
            select(Villa).where(Villa.owner_id == owner.id)
        )
        villas = villas_result.scalars().all()

        if not villas:
            await callback.message.edit_text("🏠 У тебя пока нет вилл!")
            await callback.answer()
            return

        villa_ids = [v.id for v in villas]

        bookings_result = await db.execute(
            select(Booking).where(
                Booking.villa_id.in_(villa_ids),
                Booking.status.in_(["pending", "confirmed"])
            ).order_by(Booking.checkin)
        )
        bookings = bookings_result.scalars().all()

    if not bookings:
        await callback.message.edit_text("📅 Активных броней пока нет!")
        await callback.answer()
        return

    await callback.message.edit_text(
        "📊 *Активные брони:*\n\nВыбери бронь:",
        reply_markup=bookings_keyboard(bookings),
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Просмотр брони ───────────────────────────────
@router.callback_query(F.data.startswith("view_booking_"))
async def view_booking(callback: CallbackQuery):
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

    status = "✅ Подтверждена" if booking.status == "confirmed" else "⏳ Ожидает"
    nights = (booking.checkout - booking.checkin).days

    text = (
        f"📋 *Детали брони #{booking.id}*\n\n"
        f"🏠 Вилла: {villa.name if villa else '—'}\n"
        f"📅 Заезд: {booking.checkin.strftime('%d.%m.%Y')}\n"
        f"📅 Выезд: {booking.checkout.strftime('%d.%m.%Y')}\n"
        f"🌙 Ночей: {nights}\n"
        f"👤 Клиент: {booking.client_name}\n"
        f"📱 Телефон: {booking.client_phone}\n"
        f"Статус: {status}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=booking_manage_keyboard(booking_id),
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Снятие брони ─────────────────────────────────
@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_confirm(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])
    await callback.message.edit_text(
        "🚫 *Снять бронь?*\n\nКлиент получит уведомление об отмене.",
        reply_markup=cancel_confirm_keyboard(booking_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

        if not booking:
            await callback.answer("❌ Бронь не найдена")
            return

        booking.status = "cancelled"
        client_tg_id   = booking.client_tg_id

        villa_result = await db.execute(
            select(Villa).where(Villa.id == booking.villa_id)
        )
        villa = villa_result.scalar_one_or_none()
        await db.commit()

    await callback.message.edit_text("✅ Бронь снята!")

    if BOT_CLIENT_TOKEN:
        client_bot = Bot(token=BOT_CLIENT_TOKEN)
        try:
            
            await client_bot.send_message(
                chat_id    = client_tg_id,
                text       = (
                    f"😔 *Ваша бронь была отменена хозяином*\n\n"
                    f"🏠 {villa.name if villa else '—'}\n"
                    f"📅 {booking.checkin.strftime('%d.%m.%Y')} → "
                    f"{booking.checkout.strftime('%d.%m.%Y')}\n\n"
                    "Приносим извинения. Попробуй выбрать другие даты 🌴"
                ),
                parse_mode = "Markdown"
            )
        except Exception as e:
            print(f"Ошибка уведомления клиента: {e}")
        finally:
            await client_bot.session.close()

    await callback.answer("✅ Бронь снята!")

# ─── Принять бронь ────────────────────────────────
@router.callback_query(F.data.startswith("owner_accept_"))
async def owner_accept(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

        if not booking:
            await callback.answer("❌ Бронь не найдена")
            return

        if booking.status != "pending":
            await callback.answer("⚠️ Бронь уже обработана", show_alert=True)
            return

        booking.status = "confirmed"
        await db.commit()

        client_tg_id = booking.client_tg_id
        villa_id     = booking.villa_id

        villa_result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = villa_result.scalar_one_or_none()

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Бронь подтверждена*",
        parse_mode="Markdown"
    )

    if BOT_CLIENT_TOKEN:
        client_bot = Bot(token=BOT_CLIENT_TOKEN)
        try:
            # Получаем контакт хозяина
            async with AsyncSessionLocal() as db:
                from database.models import Owner
                owner_info = await db.execute(
                    select(Owner).where(Owner.id == villa.owner_id)
                )
                owner_info = owner_info.scalar_one_or_none()

            username = f"@{owner_info.username}" if owner_info and owner_info.username else "—"

            await client_bot.send_message(
                chat_id      = client_tg_id,
                text         = (
                    f"🎉 *Бронь подтверждена!*\n\n"
                    f"🏠 {villa.name if villa else '—'}\n"
                    f"📅 {booking.checkin.strftime('%d.%m.%Y')} → "
                    f"{booking.checkout.strftime('%d.%m.%Y')}\n\n"
                    f"👤 *Контакт хозяина:* {username}\n\n"
                    "Ждём тебя! 🌴\n\n"
                    "Если во время проживания что-то понадобится — "
                    "нажми кнопку ниже 👇"
                ),
                reply_markup = client_confirmed_keyboard(villa_id),
                parse_mode   = "Markdown"
            )
        except Exception as e:
            print(f"Ошибка уведомления клиента: {e}")
        finally:
            await client_bot.session.close()

    await callback.answer("✅ Бронь подтверждена!")

# ─── Отклонить бронь ──────────────────────────────
@router.callback_query(F.data.startswith("owner_decline_"))
async def owner_decline(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

        if not booking:
            await callback.answer("❌ Бронь не найдена")
            return

        if booking.status != "pending":
            await callback.answer("⚠️ Бронь уже обработана", show_alert=True)
            return

        booking.status = "cancelled"
        await db.commit()

        client_tg_id = booking.client_tg_id
        villa_result = await db.execute(
            select(Villa).where(Villa.id == booking.villa_id)
        )
        villa = villa_result.scalar_one_or_none()

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ *Бронь отклонена*",
        parse_mode="Markdown"
    )

    if BOT_CLIENT_TOKEN:
        client_bot = Bot(token=BOT_CLIENT_TOKEN)
        try:
            await client_bot.send_message(
                chat_id    = client_tg_id,
                text       = (
                    f"😔 *К сожалению, бронь отклонена*\n\n"
                    f"🏠 {villa.name if villa else '—'}\n"
                    f"📅 {booking.checkin.strftime('%d.%m.%Y')} → "
                    f"{booking.checkout.strftime('%d.%m.%Y')}\n\n"
                    "Попробуй выбрать другие даты или виллу 🌴"
                ),
                parse_mode = "Markdown"
            )
        except Exception as e:
            print(f"Ошибка уведомления клиента: {e}")
        finally:
            await client_bot.session.close()

    await callback.answer("❌ Бронь отклонена")

# ─── Ответы хозяина на тикеты ─────────────────────
@router.callback_query(F.data.startswith("ticket_accept_"))
async def owner_ticket_accept(callback: CallbackQuery):
    await _owner_respond(callback, "ticket_accept")

@router.callback_query(F.data.startswith("ticket_30min_"))
async def owner_ticket_30min(callback: CallbackQuery):
    await _owner_respond(callback, "ticket_30min")

@router.callback_query(F.data.startswith("ticket_1hour_"))
async def owner_ticket_1hour(callback: CallbackQuery):
    await _owner_respond(callback, "ticket_1hour")

@router.callback_query(F.data.startswith("ticket_call_"))
async def owner_ticket_call(callback: CallbackQuery):
    await _owner_respond(callback, "ticket_call")

async def _owner_respond(callback: CallbackQuery, response_type: str):
    client_tg_id  = int(callback.data.split("_")[-1])
    response_text = OWNER_RESPONSES[response_type]

    await callback.message.edit_text(
        callback.message.text + f"\n\n{response_text}",
        parse_mode="Markdown"
    )

    client_bot = Bot(token=BOT_CLIENT_TOKEN)
    try:
        await client_bot.send_message(
            chat_id    = client_tg_id,
            text       = f"🔔 *Ответ хозяина:*\n\n{response_text}",
            parse_mode = "Markdown"
        )
    except Exception as e:
        print(f"Ошибка уведомления клиента: {e}")
    finally:
        await client_bot.session.close()

    await callback.answer("✅ Ответ отправлен клиенту")