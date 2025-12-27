import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from config import get_settings

from keyboards import user_menu, admin_menu, parts_menu, pagination_menu, channels_inline
from db import (
    ensure_user, add_film, add_part, delete_film_or_part, get_film_by_code, list_parts,
    log_view, top_films, user_stats, list_films_paginated, films_count,
    add_channel, del_channel, list_channels, is_owner, get_admin,
    add_admin_with_permissions, list_admins, SessionLocal, User
)

user_router = Router()
admin_router = Router()

# --- States ---
class SearchFilm(StatesGroup):
    waiting_code = State()
    choose_part = State()

class AddFilmState(StatesGroup):
    code = State()
    title = State()
    description = State()
    video = State()

class AddPartState(StatesGroup):
    code = State()
    name = State()
    description = State()
    video = State()

class DeleteFilmState(StatesGroup):
    input = State()

class ChannelsState(StatesGroup):
    mode = State()
    adding_title = State()
    adding_link = State()
    adding_private = State()
    adding_order = State()

class BroadcastState(StatesGroup):
    waiting_content = State()

class AddAdminState(StatesGroup):
    admin_id = State()
    perms = State()

class FilmStatState(StatesGroup):
    page = State()

settings = get_settings()

# --- Menus ---
async def show_user_menu(message: types.Message):
    await message.answer("Asosiy bo'lim:", reply_markup=user_menu())

async def show_admin_menu(message: types.Message):
    tg_id = message.from_user.id
    if await is_owner(tg_id):
        await message.answer("Admin menyu:", reply_markup=admin_menu())
        return
    adm = await get_admin(tg_id)
    if not adm:
        await message.answer("Sizda admin huquqlari yo'q.", reply_markup=user_menu())
        return
    await message.answer("Admin menyu: ruxsat berilgan tugmalardan foydalaning.", reply_markup=admin_menu())

# --- User Handlers ---
@user_router.message(CommandStart())
async def start(message: types.Message):
    await ensure_user(message.from_user.id)
    await message.answer("Xush kelibsiz! Kino bot foydalanuvchi menyusi.", reply_markup=user_menu())

@user_router.message(F.text == "Adminga murojat")
async def contact_admin(message: types.Message):
    await message.answer("Adminga murojat uchun havola: https://t.me/kino_vibe_films_deb")
    await show_user_menu(message)

@user_router.message(F.text == "Kinolar statistikasi")
async def films_stat(message: types.Message):
    data = await top_films(20)
    if not data:
        await message.answer("Hozircha statistika yo‘q.")
        return await show_user_menu(message)
    lines = [f"{idx}. {title} (kod: {code}) — {cnt} marta ko‘rilgan"
             for idx, (code, title, cnt) in enumerate(data, start=1)]
    await message.answer("\n".join(lines))
    await show_user_menu(message)

# --- Admin Handlers ---
@admin_router.message(Command("admin"))
async def admin_entry(message: types.Message):
    tg_id = message.from_user.id
    if await is_owner(tg_id) or (await get_admin(tg_id)):
        await show_admin_menu(message)
    else:
        await message.answer("Admin menyuga kirish taqiqlangan.", reply_markup=user_menu())

@admin_router.message(F.text == "Main menu")
async def admin_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await show_admin_menu(message)

# Film qo‘shish tugallanganda
@admin_router.message(AddFilmState.video, F.video)
async def add_film_get_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ok, msg = await add_film(
        code=data["code"], title=data["title"],
        description=data["description"], video_file_id=message.video.file_id
    )
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message)

# Qism qo‘shish tugallanganda
@admin_router.message(AddPartState.video, F.video)
async def add_parts_get_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ok, msg = await add_part(
        code=data["code"], name=data["name"],
        description=data["description"], video_file_id=message.video.file_id
    )
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message)

# Film o‘chirish tugallanganda
@admin_router.message(DeleteFilmState.input)
async def delete_film_do(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if "|" in raw:
        code, part = [x.strip() for x in raw.split("|", 1)]
        ok, msg = await delete_film_or_part(code, part)
    else:
        ok, msg = await delete_film_or_part(raw, None)
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message)

# Kanallar qo‘shish tugallanganda
@admin_router.message(ChannelsState.adding_order)
async def channels_add_order(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    order = None
    chat_id = None
    if "|" in raw:
        left, right = [x.strip() for x in raw.split("|", 1)]
        order = int(left)
        try:
            chat_id = int(right)
        except:
            chat_id = None
    else:
        order = int(raw)

    data = await state.get_data()
    title = data["title"]
    link = data["link"]
    is_private = data["is_private"]

    if not is_private and chat_id is None and link.startswith("@"):
        try:
            cm_chat = await message.bot.get_chat(link)
            chat_id = cm_chat.id
        except Exception as e:
            logging.warning(f"Public chat_id resolve failed for {link}: {e}")

    ok, msg = await add_channel(title=title, link=link, is_private=is_private, order=order, chat_id=chat_id)
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message)

# Broadcast tugallanganda
@admin_router.message(BroadcastState.waiting_content)
async def all_write_do(message: types.Message, state: FSMContext):
    sent = 0
    async with SessionLocal() as s:
        users = await s.scalars(select(User.tg_id))
        ids = list(users)
    for uid in ids:
        try:
            if message.text:
                await message.bot.send_message(uid, message.text)
            elif message.photo:
                await message.bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                await message.bot.send_video(uid, message.video.file_id, caption=message.caption or "")
            elif message.document:
                await message.bot.send_document(uid, message.document.file_id, caption=message.caption or "")
            sent += 1
        except Exception as e:
            logging.warning(f"Broadcast to {uid} failed: {e}")
    await message.answer(f"Yuborildi: {sent} foydalanuvchiga.")
    await state.clear()
    await show_admin_menu(message)

# Admin qo‘shish tugallanganda
@admin_router.message(AddAdminState.perms)
async def add_admin_do_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_id = data["admin_id"]
    text = message.text.replace(" ", "")
    if text == "7":
        ok, msg = await add_admin_with_permissions(admin_id, full_access=True, perms={})
        await message.answer(msg)
        await state.clear()
        return await show_admin_menu(message)

    selected = set([p.strip() for p in text.split(",") if p.strip() != ""])
    perms = {
        "add_film": "1" in selected,
        "add_parts": "2" in selected,
        "delete_film": "3" in selected,
        "channels": "4" in selected,
        "user_stat": "5" in selected,
        "film_stat": "6" in selected,
        "all_write": "8" in selected,
        "add_admin": "9" in selected,
        "admin_stat": "0" in selected,
    }
    ok, msg = await add_admin_with_permissions(admin_id, full_access=False, perms=perms)
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message)

# Film statistikasi tugallanganda
async def send_film_page(message: types.Message, page: int):
    per_page = 30
    offset = page * per_page
    items = await list_films_paginated(offset, per_page)
    total = await films_count()

    if not items and page != 0:
        return await message.answer("Bu sahifada ma’lumot yo‘q.", reply_markup=pagination_menu())

    lines = []
    for i, film in enumerate(items, start=1 + offset):
        lines.append(f"{i}. {film.title} (kod: {film.code})")

    meta = f"Sahifa: {page+1} / {(total + per_page - 1)//per_page or 1}"
    text = f"{meta}\n\n" + ("\n".join(lines) if lines else "Ma’lumot yo‘q.")
    await message.answer(text, reply_markup=pagination_menu())


@admin_router.message(FilmStatState.page, F.text.in_(["Keyingi", "Oldingi", "Asosiy bo‘lim", "Asosiy bo'lim"]))
async def film_stat_nav(message: types.Message, state: FSMContext):
    if message.text in ("Asosiy bo‘lim", "Asosiy bo'lim"):
        await state.clear()
        return await show_admin_menu(message)

    data = await state.get_data()
    page = data.get("page", 0)

    if message.text == "Keyingi":
        page += 1
    elif message.text == "Oldingi" and page > 0:
        page -= 1

    await state.update_data(page=page)
    await send_film_page(message, page)
