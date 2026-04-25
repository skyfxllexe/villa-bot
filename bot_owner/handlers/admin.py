from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Owner, InviteCode, Villa
import os
import secrets
import string
from datetime import datetime, timedelta

router = Router()

from dotenv import load_dotenv

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))
def is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID

# ─── Список хозяев ────────────────────────────────
@router.message(Command("owners"))
async def list_owners(message: Message):
    if not is_admin(message):
        print(message.from_user.id)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Owner))
        owners = result.scalars().all()

    if not owners:
        await message.answer("Хозяев пока нет")
        return

    text = "👥 *Все хозяева:*\n\n"
    for o in owners:
        status = "✅" if o.is_active else "❌"
        text += (
            f"{status} {o.first_name or '—'} "
            f"(@{o.username or '—'})\n"
            f"🆔 `{o.telegram_id}`\n\n"
        )

    await message.answer(text)

# ─── Заблокировать ────────────────────────────────
@router.message(Command("ban"))
async def ban_owner(message: Message):
    if not is_admin(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование:\n`/ban TELEGRAM_ID`",
            parse_mode="Markdown"
        )
        return

    telegram_id = int(args[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Owner).where(Owner.telegram_id == telegram_id)
        )
        owner = result.scalar_one_or_none()

        if not owner:
            await message.answer("❌ Хозяин не найден")
            return

        owner.is_active = False
        name = owner.first_name
        await db.commit()

    await message.answer(f"🚫 *{name}* (`{telegram_id}`) заблокирован", parse_mode="Markdown")

# ─── Разблокировать ───────────────────────────────
@router.message(Command("unban"))
async def unban_owner(message: Message):
    if not is_admin(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование:\n`/unban TELEGRAM_ID`",
            parse_mode="Markdown"
        )
        return

    telegram_id = int(args[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Owner).where(Owner.telegram_id == telegram_id)
        )
        owner = result.scalar_one_or_none()

        if not owner:
            await message.answer("❌ Хозяин не найден")
            return

        owner.is_active = True
        name = owner.first_name
        await db.commit()

    await message.answer(f"✅ *{name}* (`{telegram_id}`) разблокирован", parse_mode="Markdown")

# ─── Генерация инвайт-кода прямо из бота ──────────
@router.message(Command("invite"))
async def generate_invite(message: Message):
    if not is_admin(message):
        return

    args  = message.text.split()
    days  = int(args[1]) if len(args) > 1 else 30

    # Генерируем код
    alphabet = (string.ascii_uppercase + string.digits)\
        .replace("0","").replace("O","")\
        .replace("1","").replace("I","")\
        .replace("L","")
    code = "".join(secrets.choice(alphabet) for _ in range(8))

    async with AsyncSessionLocal() as db:
        invite = InviteCode(
            code       = code,
            expires_at = datetime.utcnow() + timedelta(days=days)
        )
        db.add(invite)
        await db.commit()

    await message.answer(
        f"✅ *Инвайт-код создан!*\n\n"
        f"🔑 Код: `{code}`\n"
        f"⏰ Действует: *{days} дней*\n\n"
        f"📨 Ссылка:\n`https://t.me/{(await message.bot.get_me()).username}?start={code}`",
        parse_mode="Markdown"
    )


@router.message(Command("remove"))
async def remove_owner(message: Message):
    if not is_admin(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование:\n`/remove TELEGRAM_ID`",
            parse_mode="Markdown"
        )
        return

    telegram_id = int(args[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Owner).where(Owner.telegram_id == telegram_id)
        )
        owner = result.scalar_one_or_none()

        if not owner:
            await message.answer("❌ Хозяин не найден")
            return

        name = owner.first_name
        await db.delete(owner)
        await db.commit()

    await message.answer(
        f"🗑 *{name}* (`{telegram_id}`) удалён из системы",
        parse_mode="Markdown"
    )

# ─── Удалить виллу ────────────────────────────────
@router.message(Command("rmvilla"))
async def remove_villa(message: Message):
    if not is_admin(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование:\n`/rmvilla VILLA_ID`",
            parse_mode="Markdown"
        )
        return

    villa_id = int(args[1])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = result.scalar_one_or_none()

        if not villa:
            await message.answer("❌ Вилла не найдена")
            return

        name = villa.name
        await db.delete(villa)
        await db.commit()

    await message.answer(
        f"🗑 Вилла *{name}* (`{villa_id}`) удалена",
        parse_mode="Markdown"
    )

# ─── Список всех вилл ─────────────────────────────
@router.message(Command("villas"))
async def list_villas(message: Message):
    if not is_admin(message):
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Villa))
        villas = result.scalars().all()

    if not villas:
        await message.answer("Вилл пока нет")
        return

    text = "🏠 *Все виллы:*\n\n"
    for v in villas:
        status = "✅" if v.is_active else "❌"
        text += (
            f"{status} `{v.id}` — *{v.name}*\n"
            f"📍 {v.location} • 💰 {v.price_idr:,.0f} IDR\n\n"
        )

    await message.answer(text, parse_mode="Markdown")