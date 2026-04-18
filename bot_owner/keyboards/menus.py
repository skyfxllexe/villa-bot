from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Главное меню
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Каталог вилл")],
            [KeyboardButton(text="📞 Связаться с менеджером")],
            [KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="🏠 Добавить виллу")],  # ← должна быть!
        ],
        resize_keyboard=True
    )

# Кнопки виллы
def villa_card(villa_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Забронировать", callback_data=f"book_{villa_id}")],
        [InlineKeyboardButton(text="◀️ Назад к каталогу", callback_data="catalog")],
    ])

# Подтверждение брони
def confirm_booking(villa_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{villa_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="catalog")],
    ])