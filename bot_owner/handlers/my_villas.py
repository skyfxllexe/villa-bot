from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Villa, Owner
import json

router = Router()

# ─── Состояния для редактирования ─────────────────
class EditVillaForm(StatesGroup):
    choosing_field  = State()  # что редактируем
    waiting_value   = State()  # новое значение

# ─── Клавиатура списка вилл ───────────────────────
def villa_list_keyboard(villas: list) -> InlineKeyboardMarkup:
    buttons = []
    for villa in villas:
        status = "✅" if villa.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {villa.name}",
                callback_data=f"myvilla_{villa.id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── Клавиатура управления виллой ─────────────────
def villa_manage_keyboard(villa_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Снять с публикации" if is_active else "✅ Опубликовать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{villa_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_{villa_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{villa_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="my_villas")],
    ])

# ─── Клавиатура редактирования ────────────────────
def edit_keyboard(villa_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Название", callback_data=f"editfield_{villa_id}_name")],
        [InlineKeyboardButton(text="📍 Локация", callback_data=f"editfield_{villa_id}_location")],
        [InlineKeyboardButton(text="💰 Цена", callback_data=f"editfield_{villa_id}_price")],
        [InlineKeyboardButton(text="👥 Гостей", callback_data=f"editfield_{villa_id}_guests")],
        [InlineKeyboardButton(text="🛏 Спален", callback_data=f"editfield_{villa_id}_bedrooms")],
        [InlineKeyboardButton(text="📝 Описание", callback_data=f"editfield_{villa_id}_description")],
        [InlineKeyboardButton(text="✨ Удобства", callback_data=f"editfield_{villa_id}_features")],
        [InlineKeyboardButton(text="📋 Правила", callback_data=f"editfield_{villa_id}_rules")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"myvilla_{villa_id}")],
    ])

# ─── Локации ──────────────────────────────────────
def locations_keyboard(villa_id: int) -> InlineKeyboardMarkup:
    LOCATIONS = ["Семиньяк", "Чангу", "Убуд", "Нуса-Дуа", "Кута", "Джимбаран", "Санур", "Улувату", "Другое"]
    buttons = []
    row = []
    for loc in LOCATIONS:
        row.append(InlineKeyboardButton(text=loc, callback_data=f"editloc_{villa_id}_{loc}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── Подтверждение удаления ───────────────────────
def delete_confirm_keyboard(villa_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"confirmdelete_{villa_id}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"myvilla_{villa_id}")],
    ])

# ══════════════════════════════════════════════════
#  МОИ ВИЛЛЫ
# ══════════════════════════════════════════════════

async def get_owner(telegram_id: int) -> Owner | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Owner).where(Owner.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

# ─── Список вилл ──────────────────────────────────
@router.message(F.text == "📋 Мои виллы")
async def my_villas(message: Message):
    owner = await get_owner(message.from_user.id)
    if not owner:
        await message.answer("❌ Ты не авторизован!")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.owner_id == owner.id)
        )
        villas = result.scalars().all()

    if not villas:
        await message.answer(
            "🏠 У тебя пока нет вилл.\n\n"
            "Нажми *🏠 Добавить виллу* чтобы добавить первую!",
            parse_mode="Markdown"
        )
        return

    await message.answer(
        f"🏠 *Мои виллы* ({len(villas)}):\n\n"
        "✅ — опубликована\n"
        "❌ — скрыта\n\n"
        "Выбери виллу для управления:",
        reply_markup=villa_list_keyboard(villas),
        parse_mode="Markdown"
    )

# Callback для возврата к списку
@router.callback_query(F.data == "my_villas")
async def my_villas_callback(callback: CallbackQuery):
    owner = await get_owner(callback.from_user.id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.owner_id == owner.id)
        )
        villas = result.scalars().all()

    await callback.message.edit_text(
        f"🏠 *Мои виллы* ({len(villas)}):\n\n"
        "✅ — опубликована\n"
        "❌ — скрыта\n\n"
        "Выбери виллу для управления:",
        reply_markup=villa_list_keyboard(villas),
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Управление виллой ────────────────────────────
# @router.callback_query(F.data.startswith("myvilla_"))
# async def villa_manage(callback: CallbackQuery, bot: Bot):
#     villa_id = int(callback.data.split("_")[1])

#     async with AsyncSessionLocal() as db:
#         result = await db.execute(
#             select(Villa).where(Villa.id == villa_id)
#         )
#         villa = result.scalar_one_or_none()

#     if not villa:
#         await callback.answer("❌ Вилла не найдена")
#         return

#     features = "\n".join([f"  • {f}" for f in json.loads(villa.features or "[]")])
#     status   = "✅ Опубликована" if villa.is_active else "❌ Скрыта"

#     text = (
#         f"🏠 *{villa.name}*\n\n"
#         f"📍 {villa.location}\n"
#         f"💰 {villa.price_idr:,.0f} IDR/ночь\n"
#         f"👥 До {villa.guests} гостей\n"
#         f"🛏 {villa.bedrooms} спальни\n\n"
#         f"📝 {villa.description}\n\n"
#         f"✨ Удобства:\n{features}\n\n"
#         f"📋 Правила: {villa.rules}\n\n"
#         f"Статус: {status}"
#     )
#     photos = json.loads(villa.photos or "[]")
#     if photos:
#         from aiogram.types import InputMediaPhoto
#         media = [InputMediaPhoto(media=p) for p in photos]
#         await bot.send_media_group(
#             chat_id = callback.message.chat.id,
#             media   = media
#         )

#     await callback.message.edit_text(
#         text,
#         reply_markup=villa_manage_keyboard(villa_id, villa.is_active),
#         parse_mode="Markdown"
#     )
#     await callback.answer()

# ─── Включить/выключить виллу ─────────────────────
@router.callback_query(F.data.startswith("toggle_"))
async def toggle_villa(callback: CallbackQuery, bot: Bot):
    villa_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = result.scalar_one_or_none()
        villa.is_active = not villa.is_active
        await db.commit()
        status = villa.is_active

    text = "✅ Вилла опубликована!" if status else "❌ Вилла скрыта!"
    await callback.answer(text)
    await villa_manage(callback, bot)

# ─── Удалить виллу ────────────────────────────────
@router.callback_query(F.data.startswith("delete_"))
async def delete_villa(callback: CallbackQuery):
    villa_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "🗑 *Удалить виллу?*\n\n"
        "Это действие необратимо!\n"
        "Все брони по этой вилле тоже удалятся.",
        reply_markup=delete_confirm_keyboard(villa_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirmdelete_"))
async def confirm_delete(callback: CallbackQuery):
    villa_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = result.scalar_one_or_none()
        if villa:
            await db.delete(villa)
            await db.commit()

    await callback.message.edit_text("✅ Вилла удалена!")
    await callback.answer()
@router.callback_query(F.data.startswith("myvilla_"))
async def villa_manage(callback: CallbackQuery, bot: Bot):
    villa_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = result.scalar_one_or_none()

    if not villa:
        await callback.answer("❌ Вилла не найдена")
        return

    features = "\n".join([f"  • {f}" for f in json.loads(villa.features or "[]")])
    status   = "✅ Опубликована" if villa.is_active else "❌ Скрыта"
    photos   = json.loads(villa.photos or "[]")

    text = (
        f"🏠 *{villa.name}*\n\n"
        f"📍 {villa.location}\n"
        f"💰 {villa.price_idr:,.0f} IDR/месяц\n"
        f"👥 До {villa.guests} гостей\n"
        f"🛏 {villa.bedrooms} спальни\n\n"
        f"📝 {villa.description}\n\n"
        f"✨ Удобства:\n{features}\n\n"
        f"📋 Правила: {villa.rules}\n\n"
        f"Статус: {status}"
    )

    if photos:
        from aiogram.types import InputMediaPhoto
        media = []
        for i, p in enumerate(photos):
            if i == len(photos) - 1:
                # Последнее фото — с описанием
                media.append(InputMediaPhoto(
                    media      = p,
                    caption    = text,
                    parse_mode = "Markdown"
                ))
            else:
                media.append(InputMediaPhoto(media=p))

        await bot.send_media_group(
            chat_id = callback.message.chat.id,
            media   = media
        )
        # Кнопки отдельным сообщением
        await callback.message.answer(
            "⚙️ Управление:",
            reply_markup=villa_manage_keyboard(villa_id, villa.is_active)
        )
    else:
        # Нет фото — просто текст с кнопками
        await callback.message.edit_text(
            text,
            reply_markup=villa_manage_keyboard(villa_id, villa.is_active),
            parse_mode="Markdown"
        )

    await callback.answer()

# ══════════════════════════════════════════════════
#  РЕДАКТИРОВАНИЕ
# ══════════════════════════════════════════════════

FIELD_NAMES = {
    "name":        "название",
    "location":    "локацию",
    "price":       "цену в рупиях",
    "guests":      "количество гостей",
    "bedrooms":    "количество спален",
    "description": "описание",
    "features":    "удобства (через запятую)",
    "rules":       "правила проживания",
}

@router.callback_query(F.data.startswith("edit_"))
async def edit_villa(callback: CallbackQuery):
    villa_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "✏️ *Что хочешь изменить?*",
        reply_markup=edit_keyboard(villa_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("editfield_"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    _, villa_id, field = callback.data.split("_")
    villa_id = int(villa_id)

    await state.update_data(villa_id=villa_id, field=field)

    # Локацию выбираем кнопками
    if field == "location":
        await callback.message.edit_text(
            "📍 Выбери новую локацию:",
            reply_markup=locations_keyboard(villa_id)
        )
        await callback.answer()
        return

    await state.set_state(EditVillaForm.waiting_value)
    await callback.message.edit_text(
        f"✏️ Введи новое *{FIELD_NAMES.get(field, field)}*:",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Новое значение локации (кнопкой) ─────────────
@router.callback_query(F.data.startswith("editloc_"))
async def edit_location(callback: CallbackQuery):
    _, villa_id, location = callback.data.split("_", 2)
    villa_id = int(villa_id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Villa).where(Villa.id == villa_id))
        villa  = result.scalar_one_or_none()
        villa.location = location
        await db.commit()

    await callback.answer(f"✅ Локация изменена на {location}")
    await callback.message.edit_text(
        f"✅ Локация обновлена: *{location}*",
        parse_mode="Markdown"
    )

# ─── Новое значение текстом ───────────────────────
@router.message(EditVillaForm.waiting_value)
async def save_field(message: Message, state: FSMContext):
    data     = await state.get_data()
    villa_id = data["villa_id"]
    field    = data["field"]
    value    = message.text

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Villa).where(Villa.id == villa_id))
        villa  = result.scalar_one_or_none()

        if field == "price":
            if not value.replace(" ", "").isdigit():
                await message.answer("❌ Введи только число!")
                return
            villa.price_idr = float(value.replace(" ", ""))

        elif field == "guests":
            if not value.isdigit():
                await message.answer("❌ Введи только число!")
                return
            villa.guests = int(value)

        elif field == "bedrooms":
            if not value.isdigit():
                await message.answer("❌ Введи только число!")
                return
            villa.bedrooms = int(value)

        elif field == "features":
            features = [f.strip() for f in value.split(",")]
            villa.features = json.dumps(features, ensure_ascii=False)

        elif field == "name":        villa.name        = value
        elif field == "description": villa.description = value
        elif field == "rules":       villa.rules       = value

        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ *{FIELD_NAMES.get(field, field).capitalize()}* обновлено!",
        parse_mode="Markdown"
    )