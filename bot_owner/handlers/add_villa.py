from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import httpx
import json
import os



router = Router()
import os
from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ─── Состояния ────────────────────────────────────
class AddVillaForm(StatesGroup):
    waiting_photos      = State()
    waiting_name        = State()
    waiting_location    = State()
    waiting_price       = State()
    waiting_guests      = State()
    waiting_bedrooms    = State()
    waiting_description = State()
    waiting_features    = State()
    waiting_rules       = State()
    waiting_confirm     = State()

# ─── Локации для выбора ───────────────────────────
LOCATIONS = [
    "Семиньяк", "Чангу", "Убуд",
    "Нуса-Дуа", "Кута", "Джимбаран",
    "Санур", "Улувату", "Другое"
]

def locations_keyboard():
    buttons = []
    row = []
    for i, loc in enumerate(LOCATIONS):
        row.append(InlineKeyboardButton(text=loc, callback_data=f"loc_{loc}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def photos_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово, далее", callback_data="photos_done")],
        [InlineKeyboardButton(text="⏭ Без фото", callback_data="skip_photos")],
    ])

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Добавить в каталог", callback_data="villa_confirm"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="villa_edit"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="villa_cancel")]
    ])

# ─── ИИ оформляет описание, удобства, правила ─────
async def polish_villa_data(description: str, features: str, rules: str) -> dict:
    prompt = f"""
Ты помощник риелтора на Бали. Оформи данные о вилле красиво.

Описание (сырое): {description}
Удобства (сырые): {features}
Правила (сырые): {rules}

Верни JSON:
{{
    "description": "красивое описание 2-3 предложения на русском",
    "features": ["удобство 1", "удобство 2", "удобство 3"],
    "rules": "правила проживания, коротко и понятно"
}}

Только JSON, без пояснений.
"""

    async with httpx.AsyncClient() as http:
        response = await http.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        content = response.json()["choices"][0]["message"]["content"].strip()

        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content)

# ─── Превью виллы ─────────────────────────────────
def format_preview(data: dict) -> str:
    features  = "\n".join([f"  • {f}" for f in data.get("features", [])])
    price_idr = data.get("price_idr", 0)
    price_usd = round(price_idr / 16000)

    return (
        f"🏠 *{data['name']}*\n\n"
        f"📍 {data['location']}\n"
        f"💰 {price_idr:,} IDR / ночь (~${price_usd})\n"
        f"👥 До {data['guests']} гостей\n"
        f"🛏 {data['bedrooms']} спальни\n\n"
        f"📝 {data['description']}\n\n"
        f"✨ Удобства:\n{features}\n\n"
        f"📋 Правила:\n{data['rules']}"
    )

# ─── Прогресс ─────────────────────────────────────
def progress(step: int, total: int = 8) -> str:
    filled = "▓" * step
    empty  = "░" * (total - step)
    return f"`{filled}{empty}` {step}/{total}"

# ══════════════════════════════════════════════════
#  ШАГИ ОПРОСНИКА
# ══════════════════════════════════════════════════

# Старт
@router.message(F.text == "🏠 Добавить виллу")
async def start_add_villa(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(photos=[])
    await state.set_state(AddVillaForm.waiting_photos)
    await message.answer(
        "🏠 *Добавление виллы* — шаг 1 из 8\n\n"
        "📸 Отправь фото виллы.\n"
        "Можно сразу несколько!\n\n"
        f"{progress(0)}\n\n"
        "Когда закончишь — нажми кнопку 👇",
        reply_markup=photos_keyboard(),
        parse_mode="Markdown"
    )

# ─── Шаг 1 — Фото ────────────────────────────────
@router.message(AddVillaForm.waiting_photos, F.photo)
async def get_photos(message: Message, state: FSMContext):
    data   = await state.get_data()
    photos = data.get("photos", [])

    # Сохраняем file_id а не скачиваем файл
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)

    await message.answer(
        f"✅ Фото {len(photos)} добавлено!\n"
        "Отправь ещё или нажми *Готово* 👇",
        reply_markup=photos_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.in_({"photos_done", "skip_photos"}))
async def photos_done(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddVillaForm.waiting_name)
    await callback.message.edit_text(
        f"*Шаг 1 из 8 — Название*\n\n"
        f"{progress(1)}\n\n"
        "🏠 Как называется вилла?",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Шаг 2 — Название ────────────────────────────
@router.message(AddVillaForm.waiting_name)
async def get_name(message: Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("❌ Слишком короткое название, попробуй ещё раз!")
        return

    await state.update_data(name=message.text)
    await state.set_state(AddVillaForm.waiting_location)
    await message.answer(
        f"*Шаг 2 из 8 — Локация*\n\n"
        f"{progress(2)}\n\n"
        "📍 Выбери локацию виллы:",
        reply_markup=locations_keyboard(),
        parse_mode="Markdown"
    )

# ─── Шаг 3 — Локация ─────────────────────────────
@router.callback_query(F.data.startswith("loc_"))
async def get_location(callback: CallbackQuery, state: FSMContext):
    location = callback.data.replace("loc_", "")
    await state.update_data(location=location)
    await state.set_state(AddVillaForm.waiting_price)
    await callback.message.edit_text(
        f"*Шаг 3 из 8 — Цена*\n\n"
        f"{progress(3)}\n\n"
        "💰 Укажи цену за ночь в *рупиях*:\n\n"
        "Например: `3500000`",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Шаг 4 — Цена ────────────────────────────────
@router.message(AddVillaForm.waiting_price)
async def get_price(message: Message, state: FSMContext):
    price = message.text.replace(" ", "").replace(",", "")
    if not price.isdigit():
        await message.answer(
            "❌ Введи только число!\n"
            "Например: `3500000`",
            parse_mode="Markdown"
        )
        return

    price_idr = int(price)
    price_usd = round(price_idr / 16000)
    await state.update_data(price_idr=price_idr)
    await state.set_state(AddVillaForm.waiting_guests)
    await message.answer(
        f"✅ {price_idr:,} IDR (~${price_usd})\n\n"
        f"*Шаг 4 из 8 — Гости*\n\n"
        f"{progress(4)}\n\n"
        "👥 Сколько максимум гостей?\n\n"
        "Например: `6`",
        parse_mode="Markdown"
    )

# ─── Шаг 5 — Гости ───────────────────────────────
@router.message(AddVillaForm.waiting_guests)
async def get_guests(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введи только число! Например: `6`", parse_mode="Markdown")
        return

    await state.update_data(guests=int(message.text))
    await state.set_state(AddVillaForm.waiting_bedrooms)
    await message.answer(
        f"*Шаг 5 из 8 — Спальни*\n\n"
        f"{progress(5)}\n\n"
        "🛏 Сколько спален?\n\n"
        "Например: `3`",
        parse_mode="Markdown"
    )

# ─── Шаг 6 — Спальни ─────────────────────────────
@router.message(AddVillaForm.waiting_bedrooms)
async def get_bedrooms(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введи только число! Например: `3`", parse_mode="Markdown")
        return

    await state.update_data(bedrooms=int(message.text))
    await state.set_state(AddVillaForm.waiting_description)
    await message.answer(
        f"*Шаг 6 из 8 — Описание*\n\n"
        f"{progress(6)}\n\n"
        "📝 Опиши виллу свободным текстом:\n"
        "_интерьер, вид, атмосфера, расположение..._\n\n"
        "Пиши как можно подробнее — ИИ красиво оформит!",
        parse_mode="Markdown"
    )

# ─── Шаг 7 — Описание ────────────────────────────
@router.message(AddVillaForm.waiting_description)
async def get_description(message: Message, state: FSMContext):
    if len(message.text) < 20:
        await message.answer(
            "❌ Слишком коротко! Напиши хотя бы пару предложений 😊"
        )
        return

    await state.update_data(description=message.text)
    await state.set_state(AddVillaForm.waiting_features)
    await message.answer(
        f"*Шаг 7 из 8 — Удобства*\n\n"
        f"{progress(7)}\n\n"
        "✨ Перечисли удобства виллы:\n"
        "_бассейн, wi-fi, кухня, кондиционер..._\n\n"
        "Можно просто через запятую!",
        parse_mode="Markdown"
    )

# ─── Шаг 8 — Удобства ────────────────────────────
@router.message(AddVillaForm.waiting_features)
async def get_features(message: Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("❌ Укажи хотя бы пару удобств!")
        return

    await state.update_data(features_raw=message.text)
    await state.set_state(AddVillaForm.waiting_rules)
    await message.answer(
        f"*Шаг 8 из 8 — Правила*\n\n"
        f"{progress(8)}\n\n"
        "📋 Укажи правила проживания:\n"
        "_нельзя с животными, тихие часы, депозит..._\n\n"
        "Если правил нет — напиши `-`",
        parse_mode="Markdown"
    )

# ─── Финал — Правила + ИИ обработка ──────────────
@router.message(AddVillaForm.waiting_rules)
async def get_rules(message: Message, state: FSMContext):
    rules = message.text if message.text != "-" else "Без особых правил"
    await state.update_data(rules_raw=rules)

    data = await state.get_data()

    processing_msg = await message.answer("⏳ ИИ оформляет данные...")

    try:
        polished = await polish_villa_data(
            description = data["description"],
            features    = data["features_raw"],
            rules       = rules
        )

        # Собираем финальные данные
        villa_data = {
            "name":        data["name"],
            "location":    data["location"],
            "price_idr":   data["price_idr"],
            "guests":      data["guests"],
            "bedrooms":    data["bedrooms"],
            "description": polished["description"],
            "features":    polished["features"],
            "rules":       polished["rules"],
            "photos":      data.get("photos", []),
        }
        await state.update_data(villa_data=villa_data)
        await state.set_state(AddVillaForm.waiting_confirm)

        preview = format_preview(villa_data)

        await processing_msg.delete()
        await message.answer(
            f"✅ *Готово! Проверь данные:*\n\n{preview}\n\n"
            "Всё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )

    except Exception as e:
        await processing_msg.delete()
        await message.answer(f"⚠️ Ошибка: {e}\nПопробуй ещё раз.")
        await state.clear()

# ─── Подтверждение ────────────────────────────────
@router.callback_query(F.data == "villa_confirm")
async def confirm_villa(callback: CallbackQuery, state: FSMContext):
    data       = await state.get_data()
    villa_data = data["villa_data"]

    # ─── Сохраняем в БД ───────────────────────────
    from database.connection import AsyncSessionLocal
    from database.models import Villa, Owner
    import json
    from sqlalchemy import select


    async with AsyncSessionLocal() as db:
        owner_result = await db.execute(
            select(Owner).where(Owner.telegram_id == callback.from_user.id)
        )
        owner = owner_result.scalar_one_or_none()
        villa = Villa(
            owner_id    = owner.id,
            name        = villa_data["name"],
            location    = villa_data["location"],
            price_idr   = villa_data["price_idr"],
            guests      = villa_data["guests"],
            bedrooms    = villa_data["bedrooms"],
            description = villa_data["description"],
            features    = json.dumps(villa_data["features"], ensure_ascii=False),
            rules       = villa_data["rules"],
            photos      = json.dumps(villa_data["photos"], ensure_ascii=False),
            is_active   = True
        )
        db.add(villa)
        await db.commit()
        await db.refresh(villa)
        villa_id = villa.id

    await callback.message.edit_text(
        f"🎉 *Вилла добавлена в каталог!*\n\n"
        f"🏠 {villa_data['name']}\n"
        f"📍 {villa_data['location']}\n"
        f"💰 {villa_data['price_idr']:,} IDR/ночь\n"
        f"🆔 ID виллы: `{villa_id}`\n\n"
        "Появится в каталоге сразу ✅",
        parse_mode="Markdown"
    )
    await state.clear()
    await callback.answer("🎉 Добавлено!")

# ─── Изменить ─────────────────────────────────────
@router.callback_query(F.data == "villa_edit")
async def edit_villa(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✏️ Начнём заново!\n"
        "Нажми *🏠 Добавить виллу*",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Отмена ───────────────────────────────────────
@router.callback_query(F.data == "villa_cancel")
async def cancel_villa(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление виллы отменено.")
    await callback.answer()