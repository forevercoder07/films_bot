from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from typing import List

def user_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Kino qidirish")],
        [KeyboardButton(text="Kinolar statistikasi")],
        [KeyboardButton(text="Adminga murojat")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, input_field_placeholder="Tanlang")

def admin_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Add film"), KeyboardButton(text="Add parts")],
        [KeyboardButton(text="Delete film"), KeyboardButton(text="Channels")],
        [KeyboardButton(text="User Statistic"), KeyboardButton(text="Film Statistic")],
        [KeyboardButton(text="All write"), KeyboardButton(text="Add admin")],
        [KeyboardButton(text="Admin statistic"), KeyboardButton(text="Main menu")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, input_field_placeholder="Admin menyu")

def parts_menu(parts_names: List[str], include_main: bool = True) -> ReplyKeyboardMarkup:
    rows = []
    if include_main:
        rows.append([KeyboardButton(text="Asosiy video")])
    row = []
    for name in parts_names:
        row.append(KeyboardButton(text=name))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="Asosiy bo‘lim")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Qismni tanlang")

def pagination_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Oldingi"), KeyboardButton(text="Keyingi")],
        [KeyboardButton(text="Asosiy bo‘lim")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def channels_inline(ch_list: List[tuple]) -> InlineKeyboardMarkup:
    # ch_list: [(order, title, link)]
    buttons = []
    for order, title, link in ch_list:
        text = f"{order}. {title}"
        buttons.append([InlineKeyboardButton(text=text, url=link)])
    buttons.append([InlineKeyboardButton(text="Tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
