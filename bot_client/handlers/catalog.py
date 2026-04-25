from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Villa
import json

router = Router()

# ─── Фильтры пользователей ────────────────────────
user_filters = {}

# ─── Клавиатуры ───────────────────────────────────
def filters_keyboard(filters: dict) -> InlineKeyboardMarkup:
    location  = filters.get("location", "Любая")
    bedrooms  = filters.get("bedrooms", "Любое")
    guests    = filters.get("guests",   "Любое")
    max_price = filters.get("max_price","Любая")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📍 Локация: {location}",
            callback_data="filter_location"
        )],
        [InlineKeyboardButton(
            text=f"🛏 Спален от: {bedrooms}",
            callback_data="filter_bedrooms"
        )],
        [InlineKeyboardButton(
            text=f"👥 Гостей от: {guests}",
            callback_data="filter_guests"
        )],
        [InlineKeyboardButton(
            text=f"💰 Макс. цена: {max_price}",
            callback_data="filter_price"
        )],
        [InlineKeyboardButton(text="🔄 Сбросить", callback_data="filter_reset")],
        [InlineKeyboardButton(text="🔍 Показать виллы", callback_data="filter_search")],
    ])

def location_keyboard() -> InlineKeyboardMarkup:
    locations = ["Семиньяк", "Чангу", "Убуд", "Нуса-Дуа", "Кута", "Джимбаран", "Санур", "Улувату"]
    buttons   = []
    row       = []
    for loc in locations:
        row.append(InlineKeyboardButton(text=loc, callback_data=f"loc_filter_{loc}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="filter_back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def bedrooms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1+", callback_data="bed_filter_1"),
            InlineKeyboardButton(text="2+", callback_data="bed_filter_2"),
            InlineKeyboardButton(text="3+", callback_data="bed_filter_3"),
        ],
        [
            InlineKeyboardButton(text="4+", callback_data="bed_filter_4"),
            InlineKeyboardButton(text="5+", callback_data="bed_filter_5"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="filter_back")],
    ])

def guests_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="2+",  callback_data="guests_filter_2"),
            InlineKeyboardButton(text="4+",  callback_data="guests_filter_4"),
            InlineKeyboardButton(text="6+",  callback_data="guests_filter_6"),
        ],
        [
            InlineKeyboardButton(text="8+",  callback_data="guests_filter_8"),
            InlineKeyboardButton(text="10+", callback_data="guests_filter_10"),
            InlineKeyboardButton(text="12+", callback_data="guests_filter_12"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="filter_back")],
    ])

def price_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="до 1,000,000 IDR",  callback_data="price_filter_1000000")],
        [InlineKeyboardButton(text="до 2,000,000 IDR",  callback_data="price_filter_2000000")],
        [InlineKeyboardButton(text="до 5,000,000 IDR",  callback_data="price_filter_5000000")],
        [InlineKeyboardButton(text="до 10,000,000 IDR", callback_data="price_filter_10000000")],
        [InlineKeyboardButton(text="Любая",              callback_data="price_filter_0")],
        [InlineKeyboardButton(text="◀️ Назад",           callback_data="filter_back")],
    ])

# ─── Главный экран фильтров ───────────────────────
@router.message(F.text == "🏠 Каталог вилл")
async def show_filters(message: Message):
    user_id = message.from_user.id
    if user_id not in user_filters:
        user_filters[user_id] = {}

    await message.answer(
        "🔍 *Поиск вилл*\n\n"
        "Настрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard(user_filters[user_id]),
        parse_mode="Markdown"
    )

# ─── Локация ──────────────────────────────────────
@router.callback_query(F.data == "filter_location")
async def filter_location(callback: CallbackQuery):
    await callback.message.edit_text(
        "📍 Выбери локацию:",
        reply_markup=location_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("loc_filter_"))
async def set_location(callback: CallbackQuery):
    user_id  = callback.from_user.id
    location = callback.data.replace("loc_filter_", "")
    user_filters.setdefault(user_id, {})["location"] = location
    await callback.message.edit_text(
        "🔍 *Поиск вилл*\n\nНастрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard(user_filters[user_id]),
        parse_mode="Markdown"
    )
    await callback.answer(f"✅ {location}")

# ─── Спальни ──────────────────────────────────────
@router.callback_query(F.data == "filter_bedrooms")
async def filter_bedrooms(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛏 Минимальное количество спален:",
        reply_markup=bedrooms_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("bed_filter_"))
async def set_bedrooms(callback: CallbackQuery):
    user_id  = callback.from_user.id
    bedrooms = int(callback.data.replace("bed_filter_", ""))
    user_filters.setdefault(user_id, {})["bedrooms"] = bedrooms
    await callback.message.edit_text(
        "🔍 *Поиск вилл*\n\nНастрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard(user_filters[user_id]),
        parse_mode="Markdown"
    )
    await callback.answer(f"✅ Спален: {bedrooms}+")

# ─── Гости ────────────────────────────────────────
@router.callback_query(F.data == "filter_guests")
async def filter_guests(callback: CallbackQuery):
    await callback.message.edit_text(
        "👥 Минимальное количество гостей:",
        reply_markup=guests_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("guests_filter_"))
async def set_guests(callback: CallbackQuery):
    user_id = callback.from_user.id
    guests  = int(callback.data.replace("guests_filter_", ""))
    user_filters.setdefault(user_id, {})["guests"] = guests
    await callback.message.edit_text(
        "🔍 *Поиск вилл*\n\nНастрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard(user_filters[user_id]),
        parse_mode="Markdown"
    )
    await callback.answer(f"✅ Гостей: {guests}+")

# ─── Цена ─────────────────────────────────────────
@router.callback_query(F.data == "filter_price")
async def filter_price(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 Максимальная цена за месяц:",
        reply_markup=price_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("price_filter_"))
async def set_price(callback: CallbackQuery):
    user_id   = callback.from_user.id
    max_price = int(callback.data.replace("price_filter_", ""))
    if max_price == 0:
        user_filters.setdefault(user_id, {}).pop("max_price", None)
        label = "Любая"
    else:
        user_filters.setdefault(user_id, {})["max_price"] = max_price
        label = f"{max_price:,} IDR"
    await callback.message.edit_text(
        "🔍 *Поиск вилл*\n\nНастрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard(user_filters[user_id]),
        parse_mode="Markdown"
    )
    await callback.answer(f"✅ Цена: до {label}")

# ─── Сброс ────────────────────────────────────────
@router.callback_query(F.data == "filter_reset")
async def reset_filters(callback: CallbackQuery):
    user_filters[callback.from_user.id] = {}
    await callback.message.edit_text(
        "🔍 *Поиск вилл*\n\nНастрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard({}),
        parse_mode="Markdown"
    )
    await callback.answer("🔄 Сброшено")

# ─── Назад ────────────────────────────────────────
@router.callback_query(F.data == "filter_back")
async def filter_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    filters = user_filters.get(user_id, {})
    await callback.message.edit_text(
        "🔍 *Поиск вилл*\n\nНастрой фильтры и нажми *Показать виллы* 👇",
        reply_markup=filters_keyboard(filters),
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Поиск ────────────────────────────────────────
@router.callback_query(F.data == "filter_search")
async def search_villas(callback: CallbackQuery):
    user_id = callback.from_user.id
    filters = user_filters.get(user_id, {})

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.is_active == True)
        )
        villas = result.scalars().all()

    # Применяем фильтры
    if filters.get("location"):
        villas = [v for v in villas if v.location == filters["location"]]
    if filters.get("bedrooms"):
        villas = [v for v in villas if v.bedrooms >= filters["bedrooms"]]
    if filters.get("guests"):
        villas = [v for v in villas if v.guests >= filters["guests"]]
    if filters.get("max_price"):
        villas = [v for v in villas if v.price_idr <= filters["max_price"]]

    if not villas:
        await callback.answer("😔 Вилл по таким фильтрам нет", show_alert=True)
        return

    await callback.message.edit_text(
        f"🏠 *Найдено вилл: {len(villas)}*",
        parse_mode="Markdown"
    )

    for villa in villas:
        features  = " • ".join(json.loads(villa.features or "[]")[:3])
        price_usd = round(villa.price_idr / 16000)
        text = (
            f"🏠 *{villa.name}*\n"
            f"📍 {villa.location}\n"
            f"💰 {villa.price_idr:,.0f} IDR/месяц (~${price_usd})\n"
            f"👥 до {villa.guests} гостей • 🛏 {villa.bedrooms} спальни\n"
            f"✨ {features}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Подробнее",     callback_data=f"villa_{villa.id}")],
            [InlineKeyboardButton(text="📅 Забронировать", callback_data=f"book_{villa.id}")],
        ])

        client_photos = json.loads(villa.client_photos or "[]")
        if client_photos:
            if len(client_photos) == 1:
                await callback.message.answer_photo(
                    photo        = client_photos[0],
                    caption      = text,
                    reply_markup = keyboard,
                    parse_mode   = "Markdown"
                )
            else:
                media = []
                for i, p in enumerate(client_photos):
                    if i == len(client_photos) - 1:
                        media.append(InputMediaPhoto(media=p, caption=text, parse_mode="Markdown"))
                    else:
                        media.append(InputMediaPhoto(media=p))
                await callback.message.answer_media_group(media=media)
                await callback.message.answer("👆 Выбери действие:", reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    await callback.answer()