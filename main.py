import os
import asyncio
import logging
from datetime import datetime, timedelta

from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Project modules
from db import (
    init_db,
    add_user,
    user_exists,
    get_all_user_ids,
    add_film,
    add_part,
    get_film,
    get_parts,
    db_get_part_by_id,
    increase_views,
    top_20_films_by_views,
    list_films_paginated,
    channels_list,
    add_channel,
    remove_channel,
    get_user_join_dates_stats,
    get_daily_views_stats,
    save_broadcast_job,
    add_admin,
    set_admin_permissions,
    get_admin_permissions,
)
from keyboards import (
    user_main_menu,
    admin_main_menu,
    parts_selection_keyboard,
    films_pagination_keyboard,
    channels_inline_keyboard,
)
from states import AddFilm, DeleteFilm, AddPart, Broadcast, SearchStates, AddAdminStates


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MODE = os.getenv("MODE", "polling")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PORT = int(os.getenv("PORT", "8443"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("kino_vibe")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# -------------------------
# Helper functions
# -------------------------
async def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    perms = await get_admin_permissions(user_id)
    return bool(perms)


async def has_perm(user_id: int, perm_name: str) -> bool:
    if user_id == ADMIN_ID:
        return True
    perms = await get_admin_permissions(user_id)
    return bool(perms and perm_name in perms)


async def ensure_user_registered(msg: Message):
    uid = msg.from_user.id
    if not await user_exists(uid):
        await add_user(uid)


async def check_channels_gate_for_message(msg: Message) -> bool:
    """
    If channels list is empty -> allow.
    If channels exist -> verify membership for public channels; private channels are skipped (soft gate).
    If user is missing any required public channel -> send channels keyboard and return False.
    """
    lst = await channels_list()
    if not lst:
        return True

    uid = msg.from_user.id
    not_joined = []
    for idx, ch in enumerate(lst, start=1):
        ident = ch.get("id_or_username")
        is_private = ch.get("is_private", False)
        if is_private:
            # skip strict check for private channels
            continue
        try:
            member = await bot.get_chat_member(chat_id=ident, user_id=uid)
            if member.status not in ("member", "administrator", "creator"):
                not_joined.append((idx, ch))
        except Exception:
            # if cannot check (invalid ident or private), skip
            continue

    if not_joined:
        kb = channels_inline_keyboard(await channels_list())
        await msg.answer(
            "Botdan to‘liq foydalanish uchun quyidagi kanallarga obuna bo‘ling va Tekshirish tugmasini bosing.",
            reply_markup=kb
        )
        return False
    return True


def format_top_films(items):
    if not items:
        return "Hozircha statistika mavjud emas."
    lines = []
    for i, (title, views) in enumerate(items, start=1):
        lines.append(f"{i}. {title} — {views} marta")
    return "\n".join(lines)


# -------------------------
# User handlers
# -------------------------
@dp.message(F.text == "/start")
async def cmd_start(msg: Message, state: FSMContext):
    await ensure_user_registered(msg)
    # Remove any previous keyboard and show user menu
    await msg.answer("Xush kelibsiz! Asosiy menyu:", reply_markup=ReplyKeyboardRemove())
    await msg.answer("Asosiy menyu", reply_markup=user_main_menu())
    logger.info(f"User {msg.from_user.id} started /start")


# Robust handlers: case/whitespace tolerant for reply-keyboard buttons
@dp.message(lambda m: m.text and m.text.strip().lower() == "kino qidirish")
async def user_search(msg: Message, state: FSMContext):
    await ensure_user_registered(msg)
    if not await check_channels_gate_for_message(msg):
        return
    await msg.answer("Iltimos, kino kodini kiriting (masalan: GOT yoki LOTR_1):")
    await state.set_state(SearchStates.waiting_code)


@dp.message(SearchStates.waiting_code)
async def handle_search_code(msg: Message, state: FSMContext):
    code = (msg.text or "").strip()
    film = await get_film(code)
    parts = await get_parts(code)
    if not film and not parts:
        await msg.answer("Bu kod bo‘yicha kino topilmadi. Qaytadan kod kiriting:")
        await state.set_state(SearchStates.waiting_code)
        return

    if parts and len(parts) > 1:
        await msg.answer("Qaysi qismni ko‘rmoqchisiz? Tanlang:", reply_markup=parts_selection_keyboard(parts))
        await state.update_data(code=code)
        await state.set_state(SearchStates.waiting_part_selection)
    else:
        part = parts[0] if parts else None
        if part:
            await increase_views(part["id"])
            await msg.answer_video(video=part["video"], caption=part.get("title") or film.get("title", "Kino"))
        else:
            await msg.answer(film.get("title", "Kino topildi"), disable_web_page_preview=True)
        await state.clear()


# -------------------------
# Qism tanlash handler (state saqlanadi)
# -------------------------
@dp.callback_query(SearchStates.waiting_part_selection)
async def handle_part_select(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    code = data.get("code")  # film kodi state’da saqlanadi

    try:
        part_id = int(cb.data.split(":")[-1])
    except Exception:
        await cb.answer("Noto'g'ri tugma ma'lumotlari", show_alert=True)
        return

    part = await db_get_part_by_id(part_id)
    if not part or part["film_code"] != code:
        await cb.answer("Qism topilmadi yoki kod mos emas", show_alert=True)
        return

    await increase_views(part_id)
    await cb.message.answer_video(
        video=part["video"],
        caption=f"{code} — {part.get('title', f'{part_id}-qism')}"
    )

    # State’ni tozalamaymiz — foydalanuvchi navbatdagi qismlarni ham tanlay oladi
    await cb.answer()


@dp.message(lambda m: m.text and m.text.strip().lower() == "kinolar statistikasi")
async def user_top20(msg: Message):
    await ensure_user_registered(msg)
    if not await check_channels_gate_for_message(msg):
        return
    items = await top_20_films_by_views()
    await msg.answer(format_top_films(items))


@dp.message(lambda m: m.text and m.text.strip().lower() == "adminga murojat")
async def contact_admin(msg: Message):
    await msg.answer("Adminga murojat uchun quyidagi havolaga bosing:\nhttps://t.me/kinovibe¬films_deb")


# /admin command: only admins see admin menu
@dp.message(F.text == "/admin")
async def cmd_admin(msg: Message):
    if not await is_admin(msg.from_user.id):
        await msg.answer("Sizda admin huquqi yo‘q.", reply_markup=user_main_menu())
        return
    await msg.answer("Admin menyu", reply_markup=admin_main_menu())
    logger.info(f"Admin {msg.from_user.id} opened admin menu via /admin")


# Keep "Admin" reply-button behavior consistent (calls same check)
@dp.message(F.text == "Admin")
async def admin_menu(msg: Message):
    await cmd_admin(msg)


# -------------------------
# Admin: Add film
# -------------------------
# Admin: Add film START
@dp.message(lambda m: m.text and m.text.strip().lower() == "add film")
async def admin_add_film_start(msg: Message, state: FSMContext):
    if not await has_perm(msg.from_user.id, "Add film"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    await msg.answer("Yangi kino qo‘shish uchun kodini kiriting:")
    await state.set_state(AddFilm.code)

# Admin: Add film CODE
@dp.message(AddFilm.code)
async def admin_add_film_code(msg: Message, state: FSMContext):
    code = (msg.text or "").strip()
    if not code:
        await msg.answer("Kod bo‘sh. Qayta kiriting:")
        await state.set_state(AddFilm.code)
        return
    # Takroriy kodni tekshirish
    if await get_film(code):
        await msg.answer("Bu kod allaqachon mavjud. Boshqa kod kiriting:")
        await state.set_state(AddFilm.code)
        return
    await state.update_data(code=code)
    await msg.answer("Kino nomini kiriting:")
    await state.set_state(AddFilm.title)

# Admin: Add film TITLE (finish)
@dp.message(AddFilm.title)
async def admin_add_film_title(msg: Message, state: FSMContext):
    title = (msg.text or "").strip()
    if not title:
        await msg.answer("Nom bo‘sh. Qayta kiriting:")
        await state.set_state(AddFilm.title)
        return
    data = await state.get_data()
    code = data.get("code")
    await add_film(code=code, title=title)
    await msg.answer("Kino qo‘shildi ✅")
    await state.clear()

@dp.message(AddFilm.code, F.text.in_(["Admin", "Channels", "Delete film", "Add film part", "User Statistic", "Film Statistic", "All write", "Add admin"]))
async def cancel_add_film_on_other_button(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Kino qo‘shish jarayoni to‘xtatildi.", reply_markup=admin_main_menu())

@dp.message(AddFilm.title, F.text.in_(["Admin", "Channels", "Delete film", "Add film part", "User Statistic", "Film Statistic", "All write", "Add admin"]))
async def cancel_add_film_title_on_other_button(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Kino qo‘shish jarayoni to‘xtatildi.", reply_markup=admin_main_menu())

@dp.message(AddPart.movie_code, F.text.in_(["Admin", "Channels", "Delete film", "Add film", "User Statistic", "Film Statistic", "All write", "Add admin"]))
async def cancel_add_part_on_other_button(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Qism qo‘shish jarayoni to‘xtatildi.", reply_markup=admin_main_menu())

@dp.message(AddPart.title, F.text.in_(["Admin", "Channels", "Delete film", "Add film", "User Statistic", "Film Statistic", "All write", "Add admin"]))
async def cancel_add_part_title_on_other_button(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Qism qo‘shish jarayoni to‘xtatildi.", reply_markup=admin_main_menu())

@dp.message(AddPart.video, F.text.in_(["Admin", "Channels", "Delete film", "Add film", "User Statistic", "Film Statistic", "All write", "Add admin"]))
async def cancel_add_part_video_on_other_button(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Qism qo‘shish jarayoni to‘xtatildi.", reply_markup=admin_main_menu())

# ===== Add film part tugmasi =====
@dp.message(lambda m: m.text and m.text.strip().lower() == "add film part")
async def admin_add_film_part_start(msg: Message, state: FSMContext):
    if not await has_perm(msg.from_user.id, "Add film"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    await msg.answer("Qism qo‘shish uchun film kodini kiriting:")
    await state.set_state(AddPart.movie_code)

@dp.message(AddPart.movie_code)
async def admin_add_film_part_code(msg: Message, state: FSMContext):
    code = msg.text.strip()
    await state.update_data(code=code)
    await msg.answer("Endi qism nomini kiriting:")
    await state.set_state(AddPart.title)

@dp.message(AddPart.title)
async def admin_add_film_part_title(msg: Message, state: FSMContext):
    title = msg.text.strip()
    await state.update_data(title=title)
    await msg.answer("Endi qism videosini yuboring (yoki URL kiriting).")
    await state.set_state(AddPart.video)

@dp.message(AddPart.video)
async def admin_add_film_part_video(msg: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("code")
    title = data.get("title")
    if msg.video:
        video_id = msg.video.file_id
    else:
        video_id = msg.text.strip()
    await add_part(film_code=code, title=title, description="", video=video_id)
    await msg.answer("Qism qo‘shildi ✅")
    await state.clear()



# -------------------------
# Admin: Delete film
# -------------------------
@dp.message(F.text == "Delete film")
async def admin_delete_film_start(msg: Message, state: FSMContext):
    if not await has_perm(msg.from_user.id, "Delete film"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    sample = (
        "O‘chirish namunasi:\n"
        "- Butun kino: code=GOT\n"
        "- Yagona qism: part_id=123\n"
        "Kerakli formatni kiriting."
    )
    await msg.answer(sample)
    await state.set_state(DeleteFilm.code)


@dp.message(DeleteFilm.code)
async def admin_delete_film_handle(msg: Message, state: FSMContext):
    txt = (msg.text or "").strip()
    try:
        if txt.startswith("code="):
            code = txt.split("=", 1)[1].strip()
            from db import delete_film
            await delete_film(code=code)
            await msg.answer("Kino o‘chirildi ✅")
        elif txt.startswith("part_id="):
            pid = int(txt.split("=", 1)[1])
            from db import delete_film
            await delete_film(part_id=pid)
            await msg.answer("Qism o‘chirildi ✅")
        else:
            await msg.answer("Format noto‘g‘ri. 'code=...' yoki 'part_id=...' kiriting.")
    except Exception as e:
        await msg.answer(f"O‘chirishda xato: {e}")
    await state.clear()


# -------------------------
# Admin: Channels
# -------------------------
@dp.message(F.text == "Channels")
async def admin_channels(msg: Message):
    if not await has_perm(msg.from_user.id, "Channels"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    lst = await channels_list()
    kb = channels_inline_keyboard(lst)
    await msg.answer("Majburiy kanallar ro‘yxati:", reply_markup=kb)
    await msg.answer("Kanal qo‘shish: add @username [private]\nKanal o‘chirish: del <index>")

@dp.message(F.text.regexp(r"^add\s+"))
async def admin_channels_add(msg: Message):
    if not await has_perm(msg.from_user.id, "Channels"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    parts = msg.text.split()
    try:
        ident = parts[1]
        is_private = (len(parts) > 2 and parts[2].lower() == "private")
        await add_channel(ident, title=ident, is_private=is_private)
        await msg.answer("Kanal qo‘shildi ✅")
    except Exception as e:
        await msg.answer(f"Qo‘shishda xato: {e}")

@dp.message(F.text.regexp(r"^del\s+"))
async def admin_channels_del(msg: Message):
    if not await has_perm(msg.from_user.id, "Channels"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    try:
        idx = int(msg.text.split()[1])
        await remove_channel(idx)
        await msg.answer("Kanal o‘chirildi ✅")
    except Exception as e:
        await msg.answer(f"O‘chirishda xato: {e}")

@dp.callback_query(F.data == "channels:verify")
async def channels_verify(cb: CallbackQuery):
    if await check_channels_gate_for_message(cb.message):
        await cb.message.answer("Tekshirildi ✅ Endi botdan to‘liq foydalanishingiz mumkin.")
    await cb.answer()


# -------------------------
# Admin: User Statistic
# -------------------------
@dp.message(F.text == "User Statistic")
async def admin_user_stat(msg: Message):
    if not await has_perm(msg.from_user.id, "User Statistic"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    today, week, month = await get_user_join_dates_stats()
    daily_views = await get_daily_views_stats()
    total_users = len(await get_all_user_ids())
    lines = [
        f"• Jami foydalanuvchilar: {total_users}",
        f"• Bugun qo‘shilganlar: {today}",
        f"• Oxirgi 7 kunda qo‘shilganlar: {week}",
        f"• Oxirgi 30 kunda qo‘shilganlar: {month}",
        "• Kunlik qo‘shilishlar:"
    ]
    for d, v in daily_views:
        lines.append(f"   - {d}: {v}")
    await msg.answer("\n".join(lines))


# -------------------------
# Admin: Film Statistic (paginated)
@dp.message(F.text == "Film Statistic")
async def admin_film_stat(msg: Message):
    if not await has_perm(msg.from_user.id, "Film Statistic"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")

    items, total = await list_films_paginated(page=1, page_size=30)
    lines = []
    for i, it in enumerate(items, start=1):
        parts = await get_parts(it['code'])
        if len(parts) > 1:
            lines.append(f"{i}. {it['title']} — {it['code']} ({len(parts)} qism)")
        else:
            lines.append(f"{i}. {it['title']} — {it['code']}")
    text = "\n".join(lines) or "Kinolar yo‘q."
    kb = films_pagination_keyboard(current=1, total_count=total, page_size=30)
    await msg.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("films:page:"))
async def films_page(cb: CallbackQuery):
    _, _, p = cb.data.split(":")
    page = int(p)
    items, total = await list_films_paginated(page=page, page_size=30)
    lines = []
    for i, it in enumerate(items, start=1):
        parts = await get_parts(it['code'])
        idx = (page - 1) * 30 + i
        if len(parts) > 1:
            lines.append(f"{idx}. {it['title']} — {it['code']} ({len(parts)} qism)")
        else:
            lines.append(f"{idx}. {it['title']} — {it['code']}")
    text = "\n".join(lines) or "Kinolar yo‘q."
    kb = films_pagination_keyboard(current=page, total_count=total, page_size=30)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


# -------------------------
# Admin: All write (broadcast)
# -------------------------
@dp.message(F.text == "All write")
async def admin_broadcast_start(msg: Message, state: FSMContext):
    if not await has_perm(msg.from_user.id, "All write"):
        return await msg.answer("Bu amal uchun ruxsat yo‘q.")
    await msg.answer("Barcha foydalanuvchilarga yuboriladigan kontentni yuboring (matn, rasm, video).")
    await state.set_state(Broadcast.message)

@dp.message(Broadcast.message)
async def admin_broadcast_send(msg: Message, state: FSMContext):
    users = await get_all_user_ids()
    sent, fail = 0, 0
    for uid in users:
        try:
            if msg.text:
                await bot.send_message(uid, msg.text)
            elif msg.photo:
                await bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption or "")
            elif msg.video:
                await bot.send_video(uid, msg.video.file_id, caption=msg.caption or "")
            else:
                continue
            sent += 1
        except Exception:
            fail += 1
            continue
    await save_broadcast_job(msg.from_user.id, len(users), sent, fail)
    await state.clear()
    await msg.answer(f"Yuborildi ✅ Jami: {len(users)}, muvaffaqiyatli: {sent}, xato: {fail}")

from db import get_all_admins
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ADMIN LIST
@dp.message(F.text == "Admins list")
async def admin_list(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return await msg.answer("Faqat bot egasi adminlar ro‘yxatini ko‘ra oladi.")

    admins = await get_all_admins()
    if not admins:
        return await msg.answer("Hozircha adminlar yo‘q.")

    # InlineKeyboardMarkup uchun majburiy inline_keyboard argumentini beramiz
    buttons = []
    for idx, adm in enumerate(admins, start=1):
        buttons.append([
            InlineKeyboardButton(
                text=f"{idx}-admin",
                url=f"tg://user?id={adm['admin_id']}"
            )
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await msg.answer("Adminlar ro‘yxati:", reply_markup=kb)


# -------------------------
# Admin: Add admin
# -------------------------
@dp.message(F.text == "Add admin")
async def admin_add_admin_start(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID:
        return await msg.answer("Faqat bot egasi yangi admin qo‘sha oladi.")
    sample = (
        "Yangi admin qo‘shish:\n"
        "1) Admin ID yuboring (masalan: 123456789)\n"
        "2) Ruxsatlarni vergul bilan kiriting, masalan:\n"
        "Add film, Delete film, Channels"
    )
    await msg.answer(sample)
    await state.set_state(AddAdminStates.waiting_admin_id)

@dp.message(AddAdminStates.waiting_admin_id)
async def admin_add_admin_id(msg: Message, state: FSMContext):
    try:
        aid = int(msg.text.strip())
        await state.update_data(admin_id=aid)
        await state.set_state(AddAdminStates.waiting_permissions)
        await msg.answer("Ruxsatlarni kiriting (vergul bilan):")
    except ValueError:
        await msg.answer("ID noto‘g‘ri. Iltimos raqam kiriting.")

@dp.message(AddAdminStates.waiting_permissions)
async def admin_add_admin_perms(msg: Message, state: FSMContext):
    data = await state.get_data()
    aid = data["admin_id"]
    raw = [s.strip() for s in msg.text.split(",")]
    valid_names = {"Add film", "Delete film", "Channels", "User Statistic", "Film Statistic", "All write", "Add admin"}
    perms = set([name for name in raw if name in valid_names])
    if not perms:
        return await msg.answer("Hech qanday to‘g‘ri ruxsat kiritilmadi. Qaytadan yuboring.")
    await add_admin(aid)
    await set_admin_permissions(aid, perms)
    await state.clear()
    await msg.answer(f"Yangi admin qo‘shildi ✅ ID={aid}\nRuxsatlar: {', '.join(perms)}")


# -------------------------
# DEBUG: log all incoming messages (place at end for diagnostics)
# -------------------------
@dp.message()
async def _debug_all_messages(msg: Message):
    try:
        state = await dp.current_state(chat=msg.chat.id, user=msg.from_user.id).get_state()
    except Exception:
        state = None
    logger.info(
        "DEBUG MSG from %s username=%s text=%r state=%r has_reply_markup=%s",
        msg.from_user.id,
        getattr(msg.from_user, "username", None),
        msg.text,
        state,
        bool(getattr(msg, "reply_markup", None))
    )


# -------------------------
# Webhook / Polling startup
# -------------------------
async def start_webhook_app():
    await init_db()
    if not WEBHOOK_HOST:
        raise RuntimeError("WEBHOOK_HOST is not set for webhook mode")
    await bot.set_webhook(f"{WEBHOOK_HOST}{WEBHOOK_PATH}")
    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app


async def run_polling():
    await bot.delete_webhook(drop_pending_updates=True)
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    if MODE.lower() == "polling":
        logger.info("[INFO] Running in POLLING mode")
        asyncio.run(run_polling())
    else:
        logger.info(f"[INFO] Running in WEBHOOK mode on port {PORT}, path={WEBHOOK_PATH}")

        async def main():
            app = await start_webhook_app()
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
            await site.start()
    
            # app doim ishlashi uchun
            await asyncio.Event().wait()
    
        asyncio.run(main())

