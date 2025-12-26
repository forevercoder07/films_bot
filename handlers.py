from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramForbiddenError
from logger import logger
from config import OWNER_ID, ADMIN_IDS
from db import (
    ensure_user, get_admin, add_admin, all_admins,
    add_channel, get_channels, delete_channel,
    add_film, get_film_by_code, add_film_part_db, delete_film_by_code, delete_film_part,
    film_parts_by_code, inc_view, top20_films, user_counts, film_catalog_paginated
)
from keyboards import (
    parts_keyboard, channels_check_kb,
    admin_menu_kb, permission_select_kb, channels_admin_kb
)

user_router = Router()
admin_router = Router()
channels_router = Router()

# Helpers
def has_perm(permissions: str | None, key: str, uid: int) -> bool:
    if uid == OWNER_ID or uid in ADMIN_IDS:
        return True
    if permissions == "ALL":
        return True
    if not permissions:
        return False
    allowed = {p.strip() for p in permissions.split(",") if p.strip()}
    return key in allowed

async def get_admin_permissions(uid: int) -> str | None:
    if uid == OWNER_ID or uid in ADMIN_IDS:
        return "ALL"
    adm = await get_admin(uid)
    return adm.permissions if adm else None

# User: main menu
class SearchStates(StatesGroup):
    waiting_code = State()
    choosing_part = State()

@user_router.message(F.text.in_(["/start", "Kino qidirish", "Kinolar statistikasi", "Adminga murojat"]))
async def user_main_menu(message: Message, state: FSMContext):
    await ensure_user(message.from_user.id)
    if message.text in ["/start", "Kino qidirish"]:
        await state.set_state(SearchStates.waiting_code)
        await message.answer("Kino kodini kiriting (masalan: AVENGERS-01)")
    elif message.text == "Kinolar statistikasi":
        rows = await top20_films()
        if not rows:
            await message.answer("Top 20 ro‘yxat hozircha bo‘sh.")
            return
        text = "Top 20 ko‘p ko‘rilgan kinolar:\n\n"
        for i, (title, views) in enumerate(rows, start=1):
            text += f"{i}. {title} — {views} marta\n"
        await message.answer(text)
    else:
        await message.answer("Adminga murojat uchun havola: https://t.me/kino_vibe_films")

@user_router.message(SearchStates.waiting_code, F.text.regexp(r"^[A-Za-z0-9\-_]+$"))
async def search_by_code(message: Message, state: FSMContext):
    code = message.text.strip()
    film = await get_film_by_code(code)
    if not film:
        await message.answer("Bu kod bo‘yicha kino topilmadi.")
        return
    parts = await film_parts_by_code(code)
    if not parts:
        await message.answer("Bu kino uchun qismlar hozircha yo‘q.")
        return
    await state.update_data(code=code, film_id=film.id)
    if len(parts) == 1:
        part = parts[0]
        await message.answer_video(part.file_id, caption=f"{film.title}")
        await inc_view(film.id, part.id, message.from_user.id)
        await state.clear()
    else:
        keyboard = parts_keyboard([p.part_number for p in parts])
        await state.set_state(SearchStates.choosing_part)
        await message.answer(f"Qismlardan birini tanlang: {film.title}", reply_markup=keyboard)

@user_router.callback_query(SearchStates.choosing_part, F.data.startswith("part:"))
async def send_part(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    code = data.get("code")
    film_id = data.get("film_id")
    part_no = int(cb.data.split(":")[1])
    parts = await film_parts_by_code(code)
    part = next((p for p in parts if p.part_number == part_no), None)
    if not part:
        await cb.message.answer("Ushbu qism topilmadi.")
        return
    await cb.message.answer_video(part.file_id, caption=f"Qism {part_no}")
    await inc_view(film_id, part.id, cb.from_user.id)
    await state.clear()

# Channels: user side
@channels_router.message(F.text == "/channels")
async def show_channels(message: Message):
    rules = await get_channels()
    if not rules:
        await message.answer("Majburiy kanallar yo‘q. Botdan to‘liq foydalanishingiz mumkin.")
        return
    items = [(r.id, r.title, r.invite_link) for r in rules]
    kb = channels_check_kb(items)
    await message.answer("Quyidagi kanallarga obuna bo‘ling, so‘ng Tekshirish tugmasini bosing:", reply_markup=kb)

@channels_router.callback_query(F.data == "channels:check")
async def verify_subs(cb: CallbackQuery):
    await cb.answer()
    rules = await get_channels()
    if not rules:
        await cb.message.answer("Kanal talablari yo‘q. Davom etishingiz mumkin.")
        return
    user_id = cb.from_user.id
    bot = cb.bot
    ok_count = 0
    total_required = sum(1 for r in rules if r.required)
    for r in rules:
        if not r.required:
            continue
        try:
            chat_id = r.chat_id if r.chat_id.lstrip("-").isdigit() else r.chat_id
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ("member","administrator","creator"):
                ok_count += 1
        except TelegramBadRequest:
            ok_count += 1
    if ok_count >= total_required:
        await cb.message.answer("Obuna talablari bajarildi. Botdan to‘liq foydalanishingiz mumkin.")
    else:
        await cb.message.answer("Ba’zi kanallarga obuna bo‘lmadingiz. Iltimos, ro‘yxatni tekshiring.")

# Admin menu
@admin_router.message(F.text == "/admin")
async def admin_menu(message: Message):
    perms = await get_admin_permissions(message.from_user.id)
    if not perms:
        await message.answer("Admin huquqlari yo‘q.")
        return
    await message.answer("Admin menyu:", reply_markup=admin_menu_kb())

# Add film
class AddFilmStates(StatesGroup):
    ask_code = State()
    ask_title = State()
    ask_parts = State()

@admin_router.callback_query(F.data == "admin:add_film")
async def add_film_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "add_film", cb.from_user.id):
        await cb.message.answer("Bu bo‘lim uchun ruxsat yo‘q.")
        return
    await state.set_state(AddFilmStates.ask_code)
    await cb.message.answer("Namuna:\nKod: AVENGERS-01\nIltimos, kodni kiriting:")

@admin_router.message(AddFilmStates.ask_code)
async def add_film_code(message: Message, state: FSMContext):
    code = message.text.strip()
    await state.update_data(code=code)
    await state.set_state(AddFilmStates.ask_title)
    await message.answer("Kino nomini kiriting (masalan: Avengers: Final jang):")

@admin_router.message(AddFilmStates.ask_title)
async def add_film_title(message: Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    existing = await get_film_by_code(data["code"])
    if existing:
        await message.answer("Bu kod allaqachon mavjud. Boshqa kod kiriting (/admin -> Add film).")
        await state.clear()
        return
    film = await add_film(data["code"], title)
    await state.update_data(film_id=film.id)
    await state.set_state(AddFilmStates.ask_parts)
    await message.answer("Endi qismlarni yuboring.\nNamuna:\n"
                         "Caption: 'Qism 1'\nVideo yuboring (Telegram video)\n"
                         "Tugatish uchun: 'done' deb yozing.")

@admin_router.message(AddFilmStates.ask_parts, F.text.lower() == "done")
async def add_film_parts_done(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Kino qo‘shildi va qismlar saqlandi.")

@admin_router.message(AddFilmStates.ask_parts, F.video)
async def add_film_part_video(message: Message, state: FSMContext):
    data = await state.get_data()
    caption = message.caption or ""
    import re
    m = re.search(r"Qism\s+(\d+)", caption)
    if not m:
        await message.answer("Caption’da 'Qism X' bo‘lishi shart. Masalan: Caption: 'Qism 1'")
        return
    part_no = int(m.group(1))
    file_id = message.video.file_id
    await add_film_part_db(data["film_id"], part_no, file_id)
    await message.answer(f"Qism {part_no} saqlandi.")

# Delete film
class DelFilmStates(StatesGroup):
    ask_mode = State()
    ask_code = State()
    ask_part = State()

@admin_router.callback_query(F.data == "admin:del_film")
async def del_film_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "del_film", cb.from_user.id):
        await cb.message.answer("Bu bo‘lim uchun ruxsat yo‘q.")
        return
    await state.set_state(DelFilmStates.ask_mode)
    await cb.message.answer("Namuna:\n- Butun kinoni o‘chirish: 'ALL'\n- Qismni o‘chirish: 'PART'\nIltimos, rejimni kiriting:")

@admin_router.message(DelFilmStates.ask_mode, F.text.in_(["ALL","PART"]))
async def del_film_mode(message: Message, state: FSMContext):
    await state.update_data(mode=message.text)
    await state.set_state(DelFilmStates.ask_code)
    await message.answer("Kodni kiriting (masalan: AVENGERS-01):")

@admin_router.message(DelFilmStates.ask_code)
async def del_film_code(message: Message, state: FSMContext):
    data = await state.get_data()
    code = message.text.strip()
    await state.update_data(code=code)
    if data["mode"] == "ALL":
        ok = await delete_film_by_code(code)
        await state.clear()
        await message.answer("Butun kino o‘chirildi." if ok else "Kino topilmadi.")
    else:
        await state.set_state(DelFilmStates.ask_part)
        await message.answer("Qism raqamini kiriting (masalan: 1):")

@admin_router.message(DelFilmStates.ask_part)
async def del_film_part_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        part_no = int(message.text.strip())
    except:
        await message.answer("Qism raqami noto‘g‘ri.")
        return
    ok = await delete_film_part(data["code"], part_no)
    await state.clear()
    await message.answer("Qism o‘chirildi." if ok else "Qism topilmadi.")

# Channels management
class ChannelStates(StatesGroup):
    ask_title = State()
    ask_chat_id = State()
    ask_invite = State()
    ask_private = State()
    ask_required = State()

@admin_router.callback_query(F.data == "admin:channels")
async def channels_menu(cb: CallbackQuery):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "channels", cb.from_user.id):
        await cb.message.answer("Bu bo‘lim uchun ruxsat yo‘q.")
        return
    rules = await get_channels()
    kb = channels_admin_kb([(r.id, r.title) for r in rules])
    await cb.message.answer("Majburiy kanallar boshqaruvi:", reply_markup=kb)

@admin_router.callback_query(F.data.startswith("chan:del:"))
async def channel_delete(cb: CallbackQuery):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "channels", cb.from_user.id):
        await cb.message.answer("Ruxsat yo‘q.")
        return
    rid = int(cb.data.split(":")[2])
    ok = await delete_channel(rid)
    await cb.message.answer("Kanal o‘chirildi." if ok else "Kanal topilmadi.")

@admin_router.callback_query(F.data == "chan:add")
async def channel_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "channels", cb.from_user.id):
        await cb.message.answer("Ruxsat yo‘q.")
        return
    await state.set_state(ChannelStates.ask_title)
    await cb.message.answer("Namuna:\nTitle: KinoVibe\nIltimos, title kiriting:")

@admin_router.message(ChannelStates.ask_title)
async def ch_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(ChannelStates.ask_chat_id)
    await message.answer("Chat ID yoki @username kiriting (masalan: @kinovibe yoki -1001234567890):")

@admin_router.message(ChannelStates.ask_chat_id)
async def ch_chat_id(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.text.strip())
    await state.set_state(ChannelStates.ask_invite)
    await message.answer("Invite link kiriting (ixtiyoriy). Agar bo‘lmasa 'skip' yozing:")

@admin_router.message(ChannelStates.ask_invite)
async def ch_invite(message: Message, state: FSMContext):
    invite = None if (message.text or "").lower() == "skip" else message.text.strip()
    await state.update_data(invite_link=invite)
    await state.set_state(ChannelStates.ask_private)
    await message.answer("Kanal yopiqmi? 'yes' yoki 'no' yozing:")

@admin_router.message(ChannelStates.ask_private, F.text.in_(["yes","no"]))
async def ch_private(message: Message, state: FSMContext):
    is_private = message.text == "yes"
    await state.update_data(is_private=is_private)
    await state.set_state(ChannelStates.ask_required)
    await message.answer("Obuna majburiymi? 'yes' yoki 'no' yozing:")

@admin_router.message(ChannelStates.ask_required, F.text.in_(["yes","no"]))
async def ch_required(message: Message, state: FSMContext):
    required = message.text == "yes"
    data = await state.get_data()
    await add_channel(data["title"], data["chat_id"], data["invite_link"], data["is_private"], required)
    await state.clear()
    await message.answer("Kanal qo‘shildi.")

# User Statistic
@admin_router.callback_query(F.data == "admin:user_stat")
async def user_stat(cb: CallbackQuery):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "user_stat", cb.from_user.id):
        await cb.message.answer("Ruxsat yo‘q.")
        return
    total, daily, weekly, monthly, daily_views = await user_counts()
    text = (
        "📊 Foydalanuvchi statistikasi\n"
        f"- Jami foydalanuvchilar: {total}\n"
        f"- 1 kunda qo‘shilgan: {daily}\n"
        f"- 1 haftada qo‘shilgan: {weekly}\n"
        f"- 1 oyda qo‘shilgan: {monthly}\n"
        f"- Kunlik ko‘rishlar: {daily_views}\n"
    )
    await cb.message.answer(text)

# Film Statistic
@admin_router.callback_query(F.data == "admin:film_stat")
async def film_stat_start(cb: CallbackQuery):
    await cb.answer()
    await film_stat_page(cb.message, 0)

async def film_stat_page(msg: Message, offset: int):
    films = await film_catalog_paginated(offset=offset, limit=30)
    if not films:
        await msg.answer("Katalog bo‘sh.")
        return
    text = "🎬 Katalog (30 tadan):\n\n"
    for f in films:
        text += f"- {f.title} (kod: {f.code})\n"
    next_offset = offset + 30
    if len(films) == 30:
        await msg.answer(text + f"\nSahifa tugadi. Keyingi sahifa uchun: /next_{next_offset}")
    else:
        await msg.answer(text + "\nOxiri.")

@admin_router.message(F.text.regexp(r"^/next_(\d+)$"))
async def film_stat_next(message: Message, regexp: dict):
    offset = int(regexp.group(1))
    await film_stat_page(message, offset)

# All write (broadcast)
class BroadcastStates(StatesGroup):
    waiting_type = State()
    waiting_content = State()

@admin_router.callback_query(F.data == "admin:all_write")
async def all_write_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "all_write", cb.from_user.id):
        await cb.message.answer("Ruxsat yo‘q.")
        return
    await state.set_state(BroadcastStates.waiting_type)
    await cb.message.answer("Yuborish turi: 'text', 'photo', 'video' dan birini kiriting:")

@admin_router.message(BroadcastStates.waiting_type, F.text.in_(["text","photo","video"]))
async def all_write_type(message: Message, state: FSMContext):
    await state.update_data(content_type=message.text)
    await state.set_state(BroadcastStates.waiting_content)
    if message.text == "text":
        await message.answer("Matn yuboring:")
    else:
        await message.answer("Media yuboring. Caption ixtiyoriy.")

@admin_router.message(BroadcastStates.waiting_content)
async def all_write_content(message: Message, state: FSMContext):
    data = await state.get_data()
    ctype = data["content_type"]
    # Collect user ids
    from db import SessionLocal, User
    async with SessionLocal() as s:
        res = await s.execute(User.__table__.select())
        users = [row[0] for row in res.fetchall()]
    ok = 0
    fail = 0
    for uid in users:
        try:
            if ctype == "text" and message.text:
                await message.bot.send_message(uid, message.text)
            elif ctype == "photo" and message.photo:
                await message.bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption)
            elif ctype == "video" and message.video:
                await message.bot.send_video(uid, message.video.file_id, caption=message.caption)
            else:
                fail += 1
                continue
            ok += 1
        except TelegramRetryAfter as e:
            fail += 1
            continue
        except TelegramForbiddenError:
            fail += 1
        except Exception as e:
            logger.error(f"Broadcast error to {uid}: {e}")
            fail += 1
    await state.clear()
    await message.answer(f"Yuborildi: {ok}, Xatolik: {fail}")

# Add admin
class AddAdminStates(StatesGroup):
    ask_id = State()
    choose_perms = State()

@admin_router.callback_query(F.data == "admin:add_admin")
async def add_admin_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "add_admin", cb.from_user.id):
        await cb.message.answer("Ruxsat yo‘q.")
        return
    await state.set_state(AddAdminStates.ask_id)
    await cb.message.answer("Namuna:\nID: 123456789\nIltimos, yangi admin ID sini kiriting:")

@admin_router.message(AddAdminStates.ask_id)
async def add_admin_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("ID noto‘g‘ri.")
        return
    await state.update_data(new_admin_id=uid, perms=set())
    await state.set_state(AddAdminStates.choose_perms)
    await message.answer("Qaysi tugmalardan foydalana oladi? Inline tugmalar orqali tanlang. Tugatish uchun 'Tasdiqlash' bosing.", reply_markup=permission_select_kb())

@admin_router.callback_query(AddAdminStates.choose_perms, F.data.startswith("perm:"))
async def add_admin_perms(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    _, key = cb.data.split(":")
    data = await state.get_data()
    perms: set = data.get("perms", set())
    if key == "done":
        perms_str = ",".join(sorted(perms))
        await add_admin(data["new_admin_id"], perms_str)
        await state.clear()
        await cb.message.answer("Admin qo‘shildi.")
        return
    valid = {"add_film","del_film","channels","user_stat","film_stat","all_write","add_admin","admin_stat"}
    if key in valid:
        perms.add(key)
        await state.update_data(perms=perms)
        await cb.message.answer(f"Ruxsat qo‘shildi: {key}")

# Admin statistic
@admin_router.callback_query(F.data == "admin:admin_stat")
async def admin_stat(cb: CallbackQuery):
    await cb.answer()
    perms = await get_admin_permissions(cb.from_user.id)
    if not has_perm(perms, "admin_stat", cb.from_user.id):
        await cb.message.answer("Ruxsat yo‘q.")
        return
    admins = await all_admins()
    if not admins:
        await cb.message.answer("Adminlar ro‘yxati bo‘sh.")
        return
    text = "👮 Adminlar ro‘yxati:\n\n"
    for a in admins:
        text += f"- ID: {a.user_id} — Ruxsatlar: {a.permissions or 'FULL/OWNER'}\n"
        text += f"  Lichka: tg://user?id={a.user_id}\n"
    await cb.message.answer(text)
