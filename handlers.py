import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import get_settings

from keyboards import user_menu, admin_menu, parts_menu, pagination_menu, channels_inline
from db import (
    ensure_user, add_film, add_part, delete_film_or_part, get_film_by_code, list_parts,
    log_view, top_films, user_stats, list_films_paginated, films_count,
    add_channel, del_channel, list_channels, is_owner, get_admin, add_admin_with_permissions, list_admins, SessionLocal, User
)

user_router = Router()
admin_router = Router()

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

# Foydalanuvchi uchun /start
async def show_user_menu(message: types.Message):
    await message.answer("Asosiy bo'lim:", reply_markup=user_menu())

# Admin uchun /start
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


async def need_join_channels(message: types.Message) -> bool:
    channels = await list_channels()
    if not channels:
        return False
    ch_list = [(c.order, c.title, c.link) for c in channels]
    await message.answer("Botdan to‘liq foydalanish uchun kanallarga obuna bo‘ling:", reply_markup=channels_inline(ch_list))
    return True

async def is_allowed_admin_action(tg_id: int, button_text: str) -> bool:
    if await is_owner(tg_id):
        return True
    adm = await get_admin(tg_id)
    if not adm:
        return False
    mapping = {
        "Add film": adm.can_add_film or adm.full_access,
        "Add parts": adm.can_add_parts or adm.full_access,
        "Delete film": adm.can_delete_film or adm.full_access,
        "Channels": adm.can_channels or adm.full_access,
        "User Statistic": adm.can_user_stat or adm.full_access,
        "Film Statistic": adm.can_film_stat or adm.full_access,
        "All write": adm.can_all_write or adm.full_access,
        "Add admin": adm.can_add_admin or adm.full_access,
        "Admin statistic": adm.can_admin_stat or adm.full_access,
        "Main menu": True,
    }
    return mapping.get(button_text, False)

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
    lines = []
    for idx, (code, title, cnt) in enumerate(data, start=1):
        lines.append(f"{idx}. {title} (kod: {code}) — {cnt} marta ko‘rilgan")
    await message.answer("\n".join(lines))
    await show_user_menu(message)

@user_router.message(F.text == "Kino qidirish")
async def search_start(message: types.Message, state: FSMContext):
    if await need_join_channels(message):
        return
    await state.set_state(SearchFilm.waiting_code)
    await message.answer("Kodni kiriting (masalan: KINO123):")

@user_router.message(SearchFilm.waiting_code)
async def search_code_received(message: types.Message, state: FSMContext):
    code = message.text.strip()
    film = await get_film_by_code(code)
    if not film:
        await message.answer("Bu kod bo‘yicha film topilmadi.")
        await show_user_menu(message)
        return await state.clear()

    parts = await list_parts(code)
    part_names = [p.name for p in parts]
    include_main = bool(film.video_file_id)
    if not parts and include_main:
        await message.answer(f"Topildi: {film.title}\n{film.description}")
        await message.answer_video(film.video_file_id, caption=f"{film.title} (kod: {film.code})")
        await log_view(code, message.from_user.id, None)
        await show_user_menu(message)
        return await state.clear()

    await state.update_data(code=code)
    await state.set_state(SearchFilm.choose_part)
    await message.answer(
        f"{film.title}\nQismni tanlang:",
        reply_markup=parts_menu(part_names, include_main=include_main)
    )

@user_router.message(SearchFilm.choose_part)
async def search_choose_part(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text in ("Asosiy bo‘lim", "Asosiy bo'lim"):
        await state.clear()
        return await show_user_menu(message)

    data = await state.get_data()
    code = data.get("code")
    film = await get_film_by_code(code)
    parts = await list_parts(code)
    part_names = [p.name for p in parts]

    if text == "Asosiy video":
        if film and film.video_file_id:
            await message.answer_video(film.video_file_id, caption=f"{film.title} — Asosiy video")
            await log_view(code, message.from_user.id, None)
        else:
            await message.answer("Asosiy video mavjud emas.")
        return await message.answer("Yana qism tanlashingiz mumkin.", reply_markup=parts_menu(part_names, include_main=bool(film.video_file_id)))

    if text in part_names:
        part = next(p for p in parts if p.name == text)
        await message.answer_video(part.video_file_id, caption=f"{film.title} — {part.name}")
        await log_view(code, message.from_user.id, part.name)
        return await message.answer("Yana qism tanlashingiz mumkin.", reply_markup=parts_menu(part_names, include_main=bool(film.video_file_id)))

    await message.answer("Qism noto‘g‘ri tanlandi. Qayta tanlang.", reply_markup=parts_menu(part_names, include_main=bool(film.video_file_id)))

@admin_router.message(Command("admin"))
async def admin_entry(message: types.Message):
    tg_id = message.from_user.id
    if await is_owner(tg_id) or (await get_admin(tg_id)):
        await show_admin_menu(message, tg_id)
    else:
        await message.answer("Admin menyuga kirish taqiqlangan.", reply_markup=user_menu())

@admin_router.message(F.text == "Main menu")
async def admin_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(F.text == "Add film")
async def add_film_start(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "Add film"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    await state.set_state(AddFilmState.code)
    await message.answer(
        "Film qo‘shish namunasi:\n"
        "1) Kod: KINO123\n2) Nomi: Avatar\n3) Izoh: qisqa ta’rif\n4) Video: video yuboring\n\n"
        "Avval kodni yuboring:"
    )

@admin_router.message(AddFilmState.code)
async def add_film_get_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await state.set_state(AddFilmState.title)
    await message.answer("Film nomini yuboring:")

@admin_router.message(AddFilmState.title)
async def add_film_get_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddFilmState.description)
    await message.answer("Izohni yuboring:")

@admin_router.message(AddFilmState.description)
async def add_film_get_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddFilmState.video)
    await message.answer("Endi film videosini yuboring (Video message sifatida).")

@admin_router.message(AddFilmState.video, F.video)
async def add_film_get_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ok, msg = await add_film(
        code=data["code"], title=data["title"], description=data["description"],
        video_file_id=message.video.file_id
    )
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(AddFilmState.video)
async def add_film_need_video(message: types.Message):
    await message.answer("Iltimos, video yuboring.")

@admin_router.message(F.text == "Add parts")
async def add_parts_start(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "Add parts"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    await state.set_state(AddPartState.code)
    await message.answer(
        "Qismlar qo‘shish tartibi:\n"
        "1) Film kodi (masalan: KINO123)\n2) Qism nomi (masalan: 1-qism)\n3) Izoh\n4) Video\n\n"
        "Avval film kodini yuboring:"
    )

@admin_router.message(AddPartState.code)
async def add_parts_get_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await state.set_state(AddPartState.name)
    await message.answer("Qism nomini yuboring (masalan: 1-qism):")

@admin_router.message(AddPartState.name)
async def add_parts_get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddPartState.description)
    await message.answer("Qism izohini yuboring:")

@admin_router.message(AddPartState.description)
async def add_parts_get_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddPartState.video)
    await message.answer("Endi qism videosini yuboring.")

@admin_router.message(AddPartState.video, F.video)
async def add_parts_get_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ok, msg = await add_part(
        code=data["code"], name=data["name"], description=data["description"], video_file_id=message.video.file_id
    )
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(AddPartState.video)
async def add_parts_need_video(message: types.Message):
    await message.answer("Iltimos, video yuboring.")

@admin_router.message(F.text == "Delete film")
async def delete_film_start(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "Delete film"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    await state.set_state(DeleteFilmState.input)
    await message.answer(
        "O‘chirish namunasi:\n"
        "- Butun film: KINO123\n"
        "- Bitta qism: KINO123 | 1-qism\n\n"
        "Yuboring:"
    )

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
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(F.text == "Channels")
async def channels_menu(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "Channels"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    chs = await list_channels()
    if chs:
        listing = "\n".join([f"{c.order}. {c.title} — {c.link} | chat_id: {c.chat_id or 'NOMA’LUM'} ({'yopiq' if c.is_private else 'ochiq'})" for c in chs])
    else:
        listing = "Hozircha kanallar yo‘q."
    await message.answer(
        "Kanallar bo‘limi:\n"
        "Qo‘shish: add\n"
        "O‘chirish: del\n\n"
        "Qat’iy tekshiruv uchun public kanallarda @username yetarli, private kanallarda botni kanalga admin sifatida qo‘shing va chat_id ni ishlating.\n\n"
        f"Joriy ro‘yxat:\n{listing}"
    )
    await state.set_state(ChannelsState.mode)

@admin_router.message(ChannelsState.mode, F.text.lower() == "add")
async def channels_add_start(message: types.Message, state: FSMContext):
    await state.set_state(ChannelsState.adding_title)
    await message.answer("Kanal nomini yuboring:")

@admin_router.message(ChannelsState.adding_title)
async def channels_add_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(ChannelsState.adding_link)
    await message.answer("Kanal havolasini yuboring (@username yoki invite link):")

@admin_router.message(ChannelsState.adding_link)
async def channels_add_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await state.set_state(ChannelsState.adding_private)
    await message.answer("Yopiq kanalmi? (ha/yo‘q):")

@admin_router.message(ChannelsState.adding_private)
async def channels_add_private(message: types.Message, state: FSMContext):
    val = message.text.strip().lower()
    is_private = val in ("ha", "ha.", "yes")
    await state.update_data(is_private=is_private)
    await state.set_state(ChannelsState.adding_order)
    await message.answer(
        "Tartib raqamini yuboring (1, 2, 3 ...). Public kanal bo‘lsa @username orqali chat_id aniqlanadi.\n"
        "Private bo‘lsa bot kanalga qo‘shilgan bo‘lishi kerak. Agar chat_id ni bilsangiz, tartib raqamdan keyin quyidagicha yuborishingiz mumkin:\n"
        "Masalan: 1 | -1001234567890"
    )

@admin_router.message(ChannelsState.adding_order)
async def channels_add_order(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    order = None
    chat_id = None
    if "|" in raw:
        left, right = [x.strip() for x in raw.split("|", 1)]
        try:
            order = int(left)
        except:
            return await message.answer("Butun son (tartib) yuboring.")
        try:
            chat_id = int(right)
        except:
            chat_id = None
    else:
        try:
            order = int(raw)
        except:
            return await message.answer("Butun son (tartib) yuboring.")

    data = await state.get_data()
    title = data["title"]
    link = data["link"]
    is_private = data["is_private"]

    # Agar public @username bo'lsa va chat_id kiritilmagan bo'lsa, bot orqali chat_id aniqlashga urinamiz
    if not is_private and chat_id is None and link.startswith("@"):
        try:
            cm_chat = await message.bot.get_chat(link)
            chat_id = cm_chat.id
        except Exception as e:
            logging.warning(f"Public chat_id resolve failed for {link}: {e}")

    ok, msg = await add_channel(title=title, link=link, is_private=is_private, order=order, chat_id=chat_id)
    await message.answer(msg)
    await state.clear()
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(ChannelsState.mode, F.text.lower() == "del")
async def channels_del_start(message: types.Message, state: FSMContext):
    await state.set_state(ChannelsState.adding_order)  # reuse order parser
    await message.answer("O‘chiriladigan kanal tartib raqamini yuboring:")

@admin_router.message(F.text == "User Statistic")
async def user_stat(message: types.Message):
    if not await is_allowed_admin_action(message.from_user.id, "User Statistic"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    total, today, week, month, today_views = await user_stats()
    text = (
        f"— Barcha foydalanuvchilar: {total}\n"
        f"— Bugun qo‘shilganlar: {today}\n"
        f"— Oxirgi 7 kunda qo‘shilganlar: {week}\n"
        f"— Oxirgi 30 kunda qo‘shilganlar: {month}\n"
        f"— Bugungi ko‘rishlar: {today_views}"
    )
    await message.answer(text)

@admin_router.message(F.text == "Film Statistic")
async def film_stat_start(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "Film Statistic"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    await state.set_state(FilmStatState.page)
    await state.update_data(page=0)
    await send_film_page(message, 0)

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
    await message.answer(f"{meta}\n\n" + ("\n".join(lines) if lines else "Ma’lumot yo‘q."), reply_markup=pagination_menu())

@admin_router.message(FilmStatState.page, F.text.in_(["Keyingi", "Oldingi", "Asosiy bo‘lim", "Asosiy bo'lim"]))
async def film_stat_nav(message: types.Message, state: FSMContext):
    if message.text in ("Asosiy bo‘lim", "Asosiy bo'lim"):
        await state.clear()
        return await show_admin_menu(message, message.from_user.id)
    data = await state.get_data()
    page = data.get("page", 0)
    if message.text == "Keyingi":
        page += 1
    elif message.text == "Oldingi" and page > 0:
        page -= 1
    await state.update_data(page=page)
    await send_film_page(message, page)

@admin_router.message(F.text == "All write")
async def all_write_start(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "All write"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    await state.set_state(BroadcastState.waiting_content)
    await message.answer("Barcha foydalanuvchilarga yuboriladigan kontentni yuboring (matn/rasm/video/hujjat).")

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
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(F.text == "Add admin")
async def add_admin_start(message: types.Message, state: FSMContext):
    if not await is_allowed_admin_action(message.from_user.id, "Add admin"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    await state.set_state(AddAdminState.admin_id)
    await message.answer(
        "Yangi admin ID sini yuboring (namuna: 123456789).\n"
        "ID ni to‘g‘ri yuboring (butun son)."
    )

@admin_router.message(AddAdminState.admin_id)
async def add_admin_get_id(message: types.Message, state: FSMContext):
    try:
        admin_id = int(message.text.strip())
    except:
        return await message.answer("To‘g‘ri ID yuboring (butun son).")
    await state.update_data(admin_id=admin_id)
    await state.set_state(AddAdminState.perms)
    await message.answer(
        "Admin ruxsatlari (raqamlar yuboring, '7' — hammasi):\n"
        "1: Add film\n2: Add parts\n3: Delete film\n4: Channels\n5: User Statistic\n"
        "6: Film Statistic\n8: All write\n9: Add admin\n0: Admin statistic\n\n"
        "Masalan: 1,2,5 yoki 7"
    )

@admin_router.message(AddAdminState.perms)
async def add_admin_do_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_id = data["admin_id"]
    text = message.text.replace(" ", "")
    if text == "7":
        ok, msg = await add_admin_with_permissions(admin_id, full_access=True, perms={})
        await message.answer(msg)
        await state.clear()
        return await show_admin_menu(message, message.from_user.id)

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
    await show_admin_menu(message, message.from_user.id)

@admin_router.message(F.text == "Admin statistic")
async def admin_stat(message: types.Message):
    if not await is_allowed_admin_action(message.from_user.id, "Admin statistic"):
        return await message.answer("Sizda bu amalga ruxsat yo‘q.")
    admins = await list_admins()
    if not admins:
        return await message.answer("Qo‘shimcha adminlar yo‘q.")
    lines = []
    for a in admins:
        perms = []
        if a.full_access: perms.append("ALL")
        else:
            if a.can_add_film: perms.append("Add film")
            if a.can_add_parts: perms.append("Add parts")
            if a.can_delete_film: perms.append("Delete film")
            if a.can_channels: perms.append("Channels")
            if a.can_user_stat: perms.append("User Statistic")
            if a.can_film_stat: perms.append("Film Statistic")
            if a.can_all_write: perms.append("All write")
            if a.can_add_admin: perms.append("Add admin")
            if a.can_admin_stat: perms.append("Admin statistic")
        link = f"tg://user?id={a.tg_id}"
        lines.append(f"- Admin: [{a.tg_id}]({link}) — ruxsatlar: {', '.join(perms) if perms else 'NONE'}")
    await message.answer("\n".join(lines), parse_mode="Markdown")

@user_router.callback_query(F.data == "check_subs")
async def check_subscriptions(cb: types.CallbackQuery):
    channels = await list_channels()
    if not channels:
        await cb.message.answer("Kanallar yo‘q, botdan to‘liq foydalanishingiz mumkin.")
        return await cb.answer("Tekshirildi")

    all_ok = True
    fail_reasons = []
    for ch in channels:
        # qat’iy tekshiruv: chat_id mavjud bo‘lsa aynan chat_id bilan tekshiramiz
        if ch.chat_id is not None:
            try:
                cm = await cb.message.bot.get_chat_member(chat_id=ch.chat_id, user_id=cb.from_user.id)
                if cm.status not in ("member", "administrator", "creator"):
                    all_ok = False
                    fail_reasons.append(f"{ch.title}")
            except Exception as e:
                logging.warning(f"Channel check failed for {ch.title}: {e}")
                all_ok = False
                fail_reasons.append(f"{ch.title}")
        else:
            # chat_id yo‘q — public @username bo‘lsa harakat qilamiz
            if not ch.is_private and ch.link.startswith("@"):
                try:
                    chat = await cb.message.bot.get_chat(ch.link)
                    cm = await cb.message.bot.get_chat_member(chat_id=chat.id, user_id=cb.from_user.id)
                    if cm.status not in ("member", "administrator", "creator"):
                        all_ok = False
                        fail_reasons.append(f"{ch.title}")
                except Exception as e:
                    logging.warning(f"Public channel check failed for {ch.title}: {e}")
                    all_ok = False
                    fail_reasons.append(f"{ch.title}")
            else:
                # private va chat_id yo‘q — qat’iy tekshiruv uchun obuna deb qabul qilmaymiz, xatosiz
                all_ok = False
                fail_reasons.append(f"{ch.title}")

    if all_ok:
        await cb.message.answer("Obuna muvaffaqiyatli! Endi botdan to‘liq foydalanishingiz mumkin.")
    else:
        pretty = ", ".join(fail_reasons)
        await cb.message.answer(f"Quyidagi kanallarga obuna talab qilinadi: {pretty}\nIltimos, ro‘yxatdagi tugmalardan foydalanib obuna bo‘ling va qayta tekshiring.")
    await cb.answer("Tekshirildi")
