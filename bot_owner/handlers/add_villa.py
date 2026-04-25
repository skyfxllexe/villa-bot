from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Villa, Owner
import httpx
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

router = Router()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CLIENT_BOT_TOKEN   = os.getenv("BOT_CLIENT_TOKEN")

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

LOCATIONS = [
    "Семиньяк", "Чангу", "Убуд",
    "Нуса-Дуа", "Кута", "Джимбаран",
    "Санур", "Улувату", "Другое"
]

# ─── Клавиатуры ───────────────────────────────────
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

def reedit_locations_keyboard():
    buttons = []
    row = []
    for loc in LOCATIONS:
        row.append(InlineKeyboardButton(text=loc, callback_data=f"reedit_loc_{loc}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="reedit_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def photos_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово, далее", callback_data="photos_done")],
        [InlineKeyboardButton(text="⏭ Без фото",      callback_data="skip_photos")],
    ])

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Добавить в каталог", callback_data="villa_confirm"),
            InlineKeyboardButton(text="✏️ Изменить",           callback_data="villa_edit"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="villa_cancel")]
    ])

def main_photo_keyboard(photos: list, current_main: int = 0) -> InlineKeyboardMarkup:
    buttons = []
    for i, _ in enumerate(photos):
        text = f"⭐ Фото {i+1}" if i == current_main else f"Фото {i+1}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"mainphoto_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="mainphoto_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def edit_fields_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Фото",        callback_data="reedit_photos")],
        [InlineKeyboardButton(text="🏠 Название",    callback_data="reedit_name")],
        [InlineKeyboardButton(text="📍 Локация",     callback_data="reedit_location")],
        [InlineKeyboardButton(text="💰 Цена",        callback_data="reedit_price")],
        [InlineKeyboardButton(text="👥 Гостей",      callback_data="reedit_guests")],
        [InlineKeyboardButton(text="🛏 Спальни",     callback_data="reedit_bedrooms")],
        [InlineKeyboardButton(text="📝 Описание",    callback_data="reedit_description")],
        [InlineKeyboardButton(text="✨ Удобства",    callback_data="reedit_features")],
        [InlineKeyboardButton(text="📋 Правила",     callback_data="reedit_rules")],
        [InlineKeyboardButton(text="◀️ Назад",       callback_data="reedit_back")],
    ])

def progress(step: int, total: int = 8) -> str:
    filled = "▓" * step
    empty  = "░" * (total - step)
    return f"`{filled}{empty}` {step}/{total}"

# ─── ИИ оформляет данные ──────────────────────────
async def polish_villa_data(description: str, features: str, rules: str) -> dict:
    prompt = f"""
Ты помощник риелтора на Бали. Оформи данные о вилле.

ВАЖНО: Используй ТОЛЬКО те факты которые написаны ниже.
НЕ придумывай ничего от себя. НЕ добавляй детали которых нет в тексте.

Описание (сырое): {description}
Удобства (сырые): {features}
Правила (сырые): {rules}

Верни JSON:
{{
    "description": "описание ТОЛЬКО на основе предоставленных фактов, 2-3 предложения",
    "features": ["только те удобства которые указаны"],
    "rules": "правила проживания только те что указаны"
}}

Только JSON, без пояснений
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
        result = response.json()
        if "choices" not in result:
            raise Exception(f"OpenRouter error: {result}")
        content = result["choices"][0]["message"]["content"].strip()
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

# ══════════════════════════════════════════════════
#  ШАГИ ОПРОСНИКА
# ══════════════════════════════════════════════════

@router.message(F.text == "🏠 Добавить виллу")
async def start_add_villa(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(photos=[], is_editing=False)
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

# ─── Фото ─────────────────────────────────────────
_media_group_tasks = {}

@router.message(AddVillaForm.waiting_photos, F.photo)
async def get_photos(message: Message, state: FSMContext, bot: Bot):
    data   = await state.get_data()
    photos = data.get("photos", [])
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    media_group_id = message.media_group_id or str(message.message_id)
    if media_group_id in _media_group_tasks:
        _media_group_tasks[media_group_id].cancel()

    async def send_after_delay():
        await asyncio.sleep(0.5)
        data   = await state.get_data()
        photos = data.get("photos", [])
        last_msg_id = data.get("last_photo_msg_id")
        if last_msg_id:
            try:
                await bot.delete_message(message.chat.id, last_msg_id)
            except:
                pass
        sent = await message.answer(
            f"✅ Добавлено фото: {len(photos)}\n"
            "Отправь ещё или нажми *Готово* 👇",
            reply_markup=photos_keyboard(),
            parse_mode="Markdown"
        )
        await state.update_data(last_photo_msg_id=sent.message_id)
        _media_group_tasks.pop(media_group_id, None)

    task = asyncio.create_task(send_after_delay())
    _media_group_tasks[media_group_id] = task

@router.callback_query(F.data.in_({"photos_done", "skip_photos"}))
async def photos_done(callback: CallbackQuery, state: FSMContext):
    data   = await state.get_data()
    photos = data.get("photos", [])

    # Если редактируем — возвращаемся к превью
    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        villa_data["photos"] = photos
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await callback.message.edit_text(
            f"✅ *Фото обновлены!*\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    if not photos or callback.data == "skip_photos":
        await state.set_state(AddVillaForm.waiting_name)
        await callback.message.edit_text(
            f"*Шаг 1 из 8 — Название*\n\n{progress(1)}\n\n🏠 Как называется вилла?",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    if len(photos) == 1:
        await state.set_state(AddVillaForm.waiting_name)
        await callback.message.edit_text(
            f"*Шаг 1 из 8 — Название*\n\n{progress(1)}\n\n🏠 Как называется вилла?",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await state.update_data(main_photo_index=0)
    await callback.message.edit_text(
        f"📸 У тебя {len(photos)} фото!\n\n⭐ Выбери *главное фото*:",
        reply_markup=main_photo_keyboard(photos, 0),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("mainphoto_"))
async def select_main_photo(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data == "mainphoto_done":
        await main_photo_done(callback, state)
        return
    index  = int(callback.data.split("_")[1])
    data   = await state.get_data()
    photos = data.get("photos", [])
    await state.update_data(main_photo_index=index)
    await callback.message.delete()
    await bot.send_photo(
        chat_id      = callback.message.chat.id,
        photo        = photos[index],
        caption      = f"📸 У тебя {len(photos)} фото!\n\n⭐ Выбери *главное фото*:",
        reply_markup = main_photo_keyboard(photos, index),
        parse_mode   = "Markdown"
    )
    await callback.answer()

async def main_photo_done(callback: CallbackQuery, state: FSMContext):
    data             = await state.get_data()
    photos           = data.get("photos", [])
    main_photo_index = data.get("main_photo_index", 0)
    main_photo = photos.pop(main_photo_index)
    photos.insert(0, main_photo)
    await state.update_data(photos=photos)
    await state.set_state(AddVillaForm.waiting_name)
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Главное фото выбрано!\n\n*Шаг 1 из 8 — Название*\n\n{progress(1)}\n\n🏠 Как называется вилла?",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Название ─────────────────────────────────────
@router.message(AddVillaForm.waiting_name)
async def get_name(message: Message, state: FSMContext):
    if not message.text:
        return
    if len(message.text) < 2:
        await message.answer("❌ Слишком короткое название!")
        return

    data = await state.get_data()
    await state.update_data(name=message.text)

    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        villa_data["name"] = message.text
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await message.answer(
            f"✅ *Название обновлено!*\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(AddVillaForm.waiting_location)
    await message.answer(
        f"*Шаг 2 из 8 — Локация*\n\n{progress(2)}\n\n📍 Выбери локацию виллы:",
        reply_markup=locations_keyboard(),
        parse_mode="Markdown"
    )

# ─── Локация ──────────────────────────────────────
@router.callback_query(F.data.startswith("loc_"))
async def get_location(callback: CallbackQuery, state: FSMContext):
    location = callback.data.replace("loc_", "")
    await state.update_data(location=location)
    await state.set_state(AddVillaForm.waiting_price)
    await callback.message.edit_text(
        f"*Шаг 3 из 8 — Цена*\n\n{progress(3)}\n\n💰 Укажи цену за ночь в *рупиях*:\n\nНапример: `3500000`",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Цена ─────────────────────────────────────────
@router.message(AddVillaForm.waiting_price)
async def get_price(message: Message, state: FSMContext):
    if not message.text:
        return
    price = message.text.replace(" ", "").replace(",", "")
    if not price.isdigit():
        await message.answer("❌ Введи только число! Например: `3500000`", parse_mode="Markdown")
        return

    data      = await state.get_data()
    price_idr = int(price)
    price_usd = round(price_idr / 16000)
    await state.update_data(price_idr=price_idr)

    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        villa_data["price_idr"] = price_idr
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await message.answer(
            f"✅ *Цена обновлена!* {price_idr:,} IDR (~${price_usd})\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(AddVillaForm.waiting_guests)
    await message.answer(
        f"✅ {price_idr:,} IDR (~${price_usd})\n\n*Шаг 4 из 8 — Гости*\n\n{progress(4)}\n\n👥 Сколько максимум гостей?\n\nНапример: `6`",
        parse_mode="Markdown"
    )

# ─── Гости ────────────────────────────────────────
@router.message(AddVillaForm.waiting_guests)
async def get_guests(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("❌ Введи только число! Например: `6`", parse_mode="Markdown")
        return

    data = await state.get_data()
    await state.update_data(guests=int(message.text))

    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        villa_data["guests"] = int(message.text)
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await message.answer(
            f"✅ *Количество гостей обновлено!*\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(AddVillaForm.waiting_bedrooms)
    await message.answer(
        f"*Шаг 5 из 8 — Спальни*\n\n{progress(5)}\n\n🛏 Сколько спален?\n\nНапример: `3`",
        parse_mode="Markdown"
    )

# ─── Спальни ──────────────────────────────────────
@router.message(AddVillaForm.waiting_bedrooms)
async def get_bedrooms(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("❌ Введи только число! Например: `3`", parse_mode="Markdown")
        return

    data = await state.get_data()
    await state.update_data(bedrooms=int(message.text))

    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        villa_data["bedrooms"] = int(message.text)
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await message.answer(
            f"✅ *Количество спален обновлено!*\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(AddVillaForm.waiting_description)
    await message.answer(
        f"*Шаг 6 из 8 — Описание*\n\n{progress(6)}\n\n📝 Опиши виллу свободным текстом:\n_интерьер, вид, атмосфера..._\n\nПиши подробнее — ИИ красиво оформит!",
        parse_mode="Markdown"
    )

# ─── Описание ─────────────────────────────────────
@router.message(AddVillaForm.waiting_description)
async def get_description(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 20:
        await message.answer("❌ Слишком коротко! Напиши хотя бы пару предложений 😊")
        return

    data = await state.get_data()
    await state.update_data(description=message.text)

    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        processing_msg = await message.answer("⏳ ИИ оформляет описание...")
        try:
            polished = await polish_villa_data(
                description = message.text,
                features    = ", ".join(villa_data.get("features", [])),
                rules       = villa_data.get("rules", "")
            )
            villa_data["description"] = polished["description"]
        except:
            villa_data["description"] = message.text
        finally:
            await processing_msg.delete()
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await message.answer(
            f"✅ *Описание обновлено!*\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(AddVillaForm.waiting_features)
    await message.answer(
        f"*Шаг 7 из 8 — Удобства*\n\n{progress(7)}\n\n✨ Перечисли удобства:\n_бассейн, wi-fi, кухня..._\n\nМожно через запятую!",
        parse_mode="Markdown"
    )

# ─── Удобства ─────────────────────────────────────
@router.message(AddVillaForm.waiting_features)
async def get_features(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 5:
        await message.answer("❌ Укажи хотя бы пару удобств!")
        return

    data = await state.get_data()
    await state.update_data(features_raw=message.text)

    if data.get("is_editing"):
        villa_data = data.get("villa_data", {})
        villa_data["features"] = [f.strip() for f in message.text.split(",")]
        await state.update_data(villa_data=villa_data, is_editing=False)
        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        await message.answer(
            f"✅ *Удобства обновлены!*\n\n{preview}\n\nВсё верно?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(AddVillaForm.waiting_rules)
    await message.answer(
        f"*Шаг 8 из 8 — Правила*\n\n{progress(8)}\n\n📋 Укажи правила проживания:\n_нельзя с животными, тихие часы..._\n\nЕсли правил нет — напиши `-`",
        parse_mode="Markdown"
    )

# ─── Правила + ИИ ─────────────────────────────────
@router.message(AddVillaForm.waiting_rules)
async def get_rules(message: Message, state: FSMContext):
    if not message.text:
        return
    rules = message.text if message.text != "-" else "Без особых правил"
    data  = await state.get_data()
    await state.update_data(rules_raw=rules)

    processing_msg = await message.answer("⏳ ИИ оформляет данные...")

    try:
        polished = await polish_villa_data(
            description = data["description"],
            features    = data["features_raw"],
            rules       = rules
        )

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

        # Если редактируем правила
        if data.get("is_editing"):
            old_villa_data = data.get("villa_data", {})
            old_villa_data["rules"] = polished["rules"]
            villa_data = old_villa_data
            await state.update_data(villa_data=villa_data, is_editing=False)
        else:
            await state.update_data(villa_data=villa_data)

        await state.set_state(AddVillaForm.waiting_confirm)
        preview = format_preview(villa_data)
        photos  = villa_data.get("photos", [])

        await processing_msg.delete()

        if photos and not data.get("is_editing"):
            media = [InputMediaPhoto(media=photo) for photo in photos]
            await message.answer_media_group(media=media)

        await message.answer(
            f"✅ *Готово! Проверь данные:*\n\n{preview}\n\nВсё верно?",
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

    client_photos = []
    print(f"📸 photos в villa_data: {villa_data.get('photos')}")
    print(f"🔑 CLIENT_BOT_TOKEN: {CLIENT_BOT_TOKEN[:10] if CLIENT_BOT_TOKEN else 'НЕТ'}")

    if villa_data["photos"] and CLIENT_BOT_TOKEN:
        print(f"📸 Начинаем перезалив {len(villa_data['photos'])} фото")
        client_bot = Bot(token=CLIENT_BOT_TOKEN)
        try:
            for file_id in villa_data["photos"]:
                print(f"⬇️ Скачиваем: {file_id[:20]}...")
                file      = await callback.bot.get_file(file_id)
                file_path = f"/tmp/{file_id}.jpg"
                await callback.bot.download_file(file.file_path, file_path)
                print(f"✅ Скачали: {file_path}")
                from aiogram.types import FSInputFile
                input_file = FSInputFile(file_path)
                msg = await client_bot.send_photo(
                    chat_id = callback.from_user.id,
                    photo   = input_file
                )
                client_photos.append(msg.photo[-1].file_id)
                await client_bot.delete_message(callback.from_user.id, msg.message_id)
                os.remove(file_path)
                print(f"✅ Перезалито успешно!")
        except Exception as e:
            print(f"❌ Ошибка перезалива: {e}")
        finally:
            await client_bot.session.close()
        print(f"📸 Итого client_photos: {client_photos}")
    else:
        print(f"⚠️ Пропускаем перезалив. photos={villa_data['photos']}, token={bool(CLIENT_BOT_TOKEN)}")

    async with AsyncSessionLocal() as db:
        owner_result = await db.execute(
            select(Owner).where(Owner.telegram_id == callback.from_user.id)
        )
        owner = owner_result.scalar_one_or_none()

        if not owner:
            await callback.answer("❌ Ты не авторизован!")
            return

        villa = Villa(
            owner_id      = owner.id,
            name          = villa_data["name"],
            location      = villa_data["location"],
            price_idr     = villa_data["price_idr"],
            guests        = villa_data["guests"],
            bedrooms      = villa_data["bedrooms"],
            description   = villa_data["description"],
            features      = json.dumps(villa_data["features"], ensure_ascii=False),
            rules         = villa_data["rules"],
            photos        = json.dumps(villa_data["photos"], ensure_ascii=False),
            client_photos = json.dumps(client_photos, ensure_ascii=False),
            is_active     = True
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

# ══════════════════════════════════════════════════
#  РЕДАКТИРОВАНИЕ ПОЛЕЙ
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "villa_edit")
async def edit_villa(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ *Что хочешь исправить?*",
        reply_markup=edit_fields_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_back")
async def reedit_back(callback: CallbackQuery, state: FSMContext):
    data       = await state.get_data()
    villa_data = data.get("villa_data", {})
    await state.update_data(is_editing=False)
    await state.set_state(AddVillaForm.waiting_confirm)
    preview = format_preview(villa_data)
    await callback.message.edit_text(
        f"✅ *Проверь данные:*\n\n{preview}\n\nВсё верно?",
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_photos")
async def reedit_photos(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photos=[], is_editing=True)
    await state.set_state(AddVillaForm.waiting_photos)
    await callback.message.edit_text(
        "📸 Отправь новые фото виллы:",
        reply_markup=photos_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_name")
async def reedit_name(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_name)
    await callback.message.edit_text(
        "🏠 Введи новое *название* виллы:",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_location")
async def reedit_location(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await callback.message.edit_text(
        "📍 Выбери новую *локацию*:",
        reply_markup=reedit_locations_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("reedit_loc_"))
async def reedit_set_location(callback: CallbackQuery, state: FSMContext):
    location   = callback.data.replace("reedit_loc_", "")
    data       = await state.get_data()
    villa_data = data.get("villa_data", {})
    villa_data["location"] = location
    await state.update_data(villa_data=villa_data, is_editing=False, location=location)
    await state.set_state(AddVillaForm.waiting_confirm)
    preview = format_preview(villa_data)
    await callback.message.edit_text(
        f"✅ *Локация обновлена!*\n\n{preview}\n\nВсё верно?",
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer(f"✅ {location}")

@router.callback_query(F.data == "reedit_price")
async def reedit_price(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_price)
    await callback.message.edit_text(
        "💰 Введи новую *цену* в рупиях:\n\nНапример: `3500000`",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_guests")
async def reedit_guests(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_guests)
    await callback.message.edit_text(
        "👥 Введи новое *количество гостей*:",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_bedrooms")
async def reedit_bedrooms(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_bedrooms)
    await callback.message.edit_text(
        "🛏 Введи новое *количество спален*:",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_description")
async def reedit_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_description)
    await callback.message.edit_text(
        "📝 Введи новое *описание* виллы:",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_features")
async def reedit_features(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_features)
    await callback.message.edit_text(
        "✨ Введи новые *удобства* через запятую:",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "reedit_rules")
async def reedit_rules(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_editing=True)
    await state.set_state(AddVillaForm.waiting_rules)
    await callback.message.edit_text(
        "📋 Введи новые *правила* проживания:\n\nЕсли правил нет — напиши `-`",
        parse_mode="Markdown"
    )
    await callback.answer()

# ─── Отмена ───────────────────────────────────────
@router.callback_query(F.data == "villa_cancel")
async def cancel_villa(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление виллы отменено.")
    await callback.answer()