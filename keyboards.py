from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any

# ===== User main menu =====
def user_main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Kino qidirish")],
            [KeyboardButton(text="Kinolar statistikasi")],
            [KeyboardButton(text="Adminga murojat")]
        ],
        resize_keyboard=True
    )
    return kb

# ===== Admin main menu =====
def admin_main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add film"), KeyboardButton(text="Delete film")],
            [KeyboardButton(text="Add film part"), KeyboardButton(text="Channels")],
            [KeyboardButton(text="User Statistic"), KeyboardButton(text="Film Statistic")],
            [KeyboardButton(text="All write"), KeyboardButton(text="Add admin")],
            [KeyboardButton(text="Admins list")]   # ✅ yangi tugma
        ],
        resize_keyboard=True
    )
    return kb


# ===== Parts selection inline keyboard =====
def parts_selection_keyboard(parts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for idx, p in enumerate(parts, start=1):
        buttons.append([InlineKeyboardButton(text=f"{idx}-qism", callback_data=f"part:{p.get('id')}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ===== Films pagination keyboard =====
def films_pagination_keyboard(current: int, total_count: int, page_size: int = 30) -> InlineKeyboardMarkup:
    total_pages = (total_count + page_size - 1) // page_size if total_count else 1
    row = []
    if current > 1:
        row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"films:page:{current-1}"))
    row.append(InlineKeyboardButton(text=f"{current}/{total_pages}", callback_data="noop"))
    if current < total_pages:
        row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"films:page:{current+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])

# ===== Channels inline keyboard =====


def channels_inline_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for idx, ch in enumerate(channels, start=1):
        ident = ch.get("id_or_username")
        text = f"{idx}-kanal"
        if ident and isinstance(ident, str) and ident.strip():
            url = f"https://t.me/{ident.lstrip('@')}"
            buttons.append([InlineKeyboardButton(text=text, url=url)])
    # Oxirida "Tekshirish" tugmasi
    buttons.append([InlineKeyboardButton(text="Tekshirish", callback_data="channels:verify")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


