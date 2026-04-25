from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Villa, Booking, Owner
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

router = Router()

BOT_OWNER_TOKEN = os.getenv("BOT_OWNER_TOKEN")

class BookingForm(StatesGroup):
    waiting_checkin  = State()
    waiting_checkout = State()
    waiting_name     = State()
    waiting_phone    = State()
    waiting_confirm  = State()

def confirm_booking_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="booking_confirm"),
            InlineKeyboardButton(text="❌ Отмена",      callback_data="booking_cancel"),
        ]
    ])

def owner_keyboard(booking_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять",   callback_data=f"owner_accept_{booking_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"owner_decline_{booking_id}"),
        ]
    ])

# ─── Нажали Забронировать ─────────────────────────
# ─── Нажали Забронировать ─────────────────────────
@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    villa_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Villa).where(Villa.id == villa_id))
        villa  = result.scalar_one_or_none()

        # Получаем занятые даты
        bookings_result = await db.execute(
            select(Booking).where(
                Booking.villa_id == villa_id,
                Booking.status.in_(["pending", "confirmed"])
            )
        )
        bookings = bookings_result.scalars().all()

    if not villa:
        await callback.answer("❌ Вилла не найдена")
        return

    await state.update_data(villa_id=villa_id, villa_name=villa.name)
    await state.set_state(BookingForm.waiting_checkin)

    # Формируем список занятых дат
    if bookings:
        busy_dates = "\n".join([
            f"  ❌ {b.checkin.strftime('%d.%m.%Y')} → {b.checkout.strftime('%d.%m.%Y')}"
            for b in bookings
        ])
        busy_text = f"\n\n📅 *Занятые даты:*\n{busy_dates}"
    else:
        busy_text = "\n\n✅ *Все даты свободны!*"

    await callback.message.answer(
        f"📅 *Бронирование — {villa.name}*"
        f"{busy_text}\n\n"
        "Введи дату *заезда* в формате ДД.ММ.ГГГГ\n"
        "Например: `15.07.2025`",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Дата заезда ──────────────────────────────────
@router.message(BookingForm.waiting_checkin)
async def get_checkin(message: Message, state: FSMContext):
    try:
        checkin = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат! Введи дату как `15.07.2025`", parse_mode="Markdown")
        return

    if checkin < datetime.now():
        await message.answer("❌ Дата заезда не может быть в прошлом!")
        return

    await state.update_data(checkin=checkin)
    await state.set_state(BookingForm.waiting_checkout)
    await message.answer(
        "📅 Теперь введи дату *выезда*:\n"
        "Например: `22.07.2025`",
        parse_mode="Markdown"
    )

# ─── Дата выезда ──────────────────────────────────
@router.message(BookingForm.waiting_checkout)
async def get_checkout(message: Message, state: FSMContext):
    try:
        checkout = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат! Введи дату как `22.07.2025`", parse_mode="Markdown")
        return

    data    = await state.get_data()
    checkin = data["checkin"]

    if checkout <= checkin:
        await message.answer("❌ Дата выезда должна быть позже даты заезда!")
        return

    # Проверяем доступность
    villa_id = data["villa_id"]
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.villa_id == villa_id,
                Booking.status.in_(["pending", "confirmed"]),
                Booking.checkin  < checkout,
                Booking.checkout > checkin
            )
        )
        existing = result.scalars().all()

    if existing:
        await message.answer(
            "❌ *Эти даты уже заняты!*\n\n"
            "Пожалуйста выбери другие даты.\n"
            "Введи дату заезда заново:",
            parse_mode="Markdown"
        )
        await state.set_state(BookingForm.waiting_checkin)
        return

    nights = (checkout - checkin).days
    await state.update_data(checkout=checkout, nights=nights)
    await state.set_state(BookingForm.waiting_name)

    await message.answer(
        f"✅ *Даты свободны!*\n\n"
        f"📅 {checkin.strftime('%d.%m.%Y')} → {checkout.strftime('%d.%m.%Y')}\n"
        f"🌙 Ночей: {nights}\n\n"
        "👤 Введи своё *имя и фамилию*:",
        parse_mode="Markdown"
    )

# ─── Имя ──────────────────────────────────────────
@router.message(BookingForm.waiting_name)
async def get_name(message: Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("❌ Введи имя и фамилию!")
        return

    await state.update_data(client_name=message.text)
    await state.set_state(BookingForm.waiting_phone)
    await message.answer(
        "📱 Введи свой *номер телефона*:\n"
        "Например: `+7 999 000 00 00`",
        parse_mode="Markdown"
    )

# ─── Телефон ──────────────────────────────────────
@router.message(BookingForm.waiting_phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(client_phone=message.text)
    data = await state.get_data()

    await state.set_state(BookingForm.waiting_confirm)
    await message.answer(
        f"📋 *Проверь данные брони:*\n\n"
        f"🏠 Вилла: {data['villa_name']}\n"
        f"📅 Заезд: {data['checkin'].strftime('%d.%m.%Y')}\n"
        f"📅 Выезд: {data['checkout'].strftime('%d.%m.%Y')}\n"
        f"🌙 Ночей: {data['nights']}\n"
        f"👤 Имя: {data['client_name']}\n"
        f"📱 Телефон: {data['client_phone']}\n\n"
        "Всё верно?",
        reply_markup=confirm_booking_keyboard(),
        parse_mode="Markdown"
    )

# ─── Подтверждение от клиента ─────────────────────
@router.callback_query(F.data == "booking_confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    # Сохраняем бронь в БД
    async with AsyncSessionLocal() as db:
        booking = Booking(
            villa_id     = data["villa_id"],
            client_tg_id = callback.from_user.id,
            client_name  = data["client_name"],
            client_phone = data["client_phone"],
            checkin      = data["checkin"],
            checkout     = data["checkout"],
            status       = "pending"
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        booking_id = booking.id

        # Получаем хозяина виллы
        villa_result = await db.execute(
            select(Villa).where(Villa.id == data["villa_id"])
        )
        villa = villa_result.scalar_one_or_none()

        owner_result = await db.execute(
            select(Owner).where(Owner.id == villa.owner_id)
        )
        owner = owner_result.scalar_one_or_none()
    username = f"@{owner.username}" if owner and owner.username else "уточните при заселении"

    # Сообщение клиенту
    await callback.message.edit_text(
        f"✅ *Заявка отправлена!*\n\n"
        f"🏠 {data['villa_name']}\n"
        f"📅 {data['checkin'].strftime('%d.%m.%Y')} → {data['checkout'].strftime('%d.%m.%Y')}\n"
        f"🌙 Ночей: {data['nights']}\n\n"
        f"👤 *Контакт хозяина:* {username}\n\n"
        "Ожидай подтверждения от хозяина 🙌\n"
        "Обычно отвечают в течение часа.",
        parse_mode="Markdown"
    )

    # Уведомление хозяину через первого бота
    if owner and BOT_OWNER_TOKEN:
        owner_bot = Bot(token=BOT_OWNER_TOKEN)
        try:
            await owner_bot.send_message(
                chat_id    = owner.telegram_id,
                text       = (
                    f"🔔 *Новая заявка на бронирование!*\n\n"
                    f"🏠 Вилла: {data['villa_name']}\n"
                    f"📅 Заезд: {data['checkin'].strftime('%d.%m.%Y')}\n"
                    f"📅 Выезд: {data['checkout'].strftime('%d.%m.%Y')}\n"
                    f"🌙 Ночей: {data['nights']}\n"
                    f"👤 Клиент: {data['client_name']}\n"
                    f"📱 Телефон: {data['client_phone']}\n"
                    f"💬 Telegram: @{callback.from_user.username or '—'}"
                ),
                reply_markup = owner_keyboard(booking_id),
                parse_mode   = "Markdown"
            )
        except Exception as e:
            print(f"Ошибка уведомления хозяина: {e}")
        finally:
            await owner_bot.session.close()

    await state.clear()
    await callback.answer()

# ─── Отмена брони клиентом ────────────────────────
@router.callback_query(F.data == "booking_cancel")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Бронирование отменено.")
    await callback.answer()