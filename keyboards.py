from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Kino topish")],
        [KeyboardButton(text="📊 Statistikalar")],
        [KeyboardButton(text="📩 Adminga murojaat")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="🗑 Kino o'chirish")],
        [KeyboardButton(text="➕ Kino qism qo'shish")],
        [KeyboardButton(text="📊 User statistikasi"), KeyboardButton(text="🎞 Kino statistikasi")],
        [KeyboardButton(text="📢 Xabar yuborish")],
        [KeyboardButton(text="🔙 Asosiy menyu")]
    ],
    resize_keyboard=True
)
