from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# User keyboards
def parts_keyboard(parts: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"Qism {p}", callback_data=f"part:{p}")] for p in parts]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def channels_check_kb(items: list[tuple[int, str, str | None]]):
    rows = []
    for idx, (_, title, invite) in enumerate(items, start=1):
        btn_text = f"{idx}. {title}"
        url = invite if invite else "https://t.me/"
        rows.append([InlineKeyboardButton(text=btn_text, url=url)])
    rows.append([InlineKeyboardButton(text="Tekshirish", callback_data="channels:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# Admin keyboards
def admin_menu_kb():
    rows = [
        [InlineKeyboardButton(text="Add film", callback_data="admin:add_film")],
        [InlineKeyboardButton(text="Delete film", callback_data="admin:del_film")],
        [InlineKeyboardButton(text="Channels", callback_data="admin:channels")],
        [InlineKeyboardButton(text="User Statistic", callback_data="admin:user_stat")],
        [InlineKeyboardButton(text="Film Statistic", callback_data="admin:film_stat")],
        [InlineKeyboardButton(text="All write", callback_data="admin:all_write")],
        [InlineKeyboardButton(text="Add admin", callback_data="admin:add_admin")],
        [InlineKeyboardButton(text="Admin statistic", callback_data="admin:admin_stat")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def permission_select_kb():
    opts = ["add_film","del_film","channels","user_stat","film_stat","all_write","add_admin","admin_stat"]
    rows = [[InlineKeyboardButton(text=o, callback_data=f"perm:{o}")] for o in opts]
    rows.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="perm:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def channels_admin_kb(items: list[tuple[int, str]]):
    rows = [[InlineKeyboardButton(text=f"❌ O‘chirish: {title}", callback_data=f"chan:del:{rid}")]
            for rid, title in items]
    rows.append([InlineKeyboardButton(text="➕ Kanal qo‘shish", callback_data="chan:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
