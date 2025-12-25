# import os
# import asyncio
# import logging
# from datetime import datetime, timedelta
#
# from aiogram import Bot, Dispatcher, F
# from aiogram.types import Message, CallbackQuery
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.fsm.context import FSMContext
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from aiohttp import web
# from dotenv import load_dotenv
#
# # Project modules
# from db import (
#     init_db,
#     add_user,
#     user_exists,
#     get_user_join_dates_stats,  # (today_count, week_count, month_count)
#     get_daily_views_stats,      # returns dict or list of (date, views)
#     add_film,
#     delete_film,                # supports deleting whole film or single part by id
#     get_film,
#     get_parts,
#     add_part,
#     increase_views,
#     list_films_paginated,       # (items, total_count), items include (code, title)
#     top_20_films_by_views,      # returns list of (title, views)
#     save_broadcast_job,         # optional: log broadcast
#     get_all_user_ids,
#     get_admin_permissions,      # returns set of permission keys
#     set_admin_permissions,      # save permissions for admin
#     add_admin,                  # add admin id
#     channels_list,              # returns list of dicts {id_or_username, title, is_private}
#     add_channel,                # add channel
#     remove_channel,             # remove channel by index
# )
# from keyboards import (
#     user_main_menu,
#     admin_main_menu,
#     parts_selection_keyboard,
#     films_pagination_keyboard,
#     channels_inline_keyboard,   # shows numbered channels + verify button
# )
#
# load_dotenv()
#
# BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
# MODE = os.getenv("MODE", "polling")
# WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
# WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
# PORT = int(os.getenv("PORT", "8443"))
#
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
# )
#
# bot = Bot(BOT_TOKEN)
# dp = Dispatcher()
#
# # FSM states
# class SearchStates(StatesGroup):
#     waiting_code = State()
#     waiting_part_selection = State()
#
# class AddFilmStates(StatesGroup):
#     waiting_code = State()
#     waiting_title = State()
#     waiting_single_or_parts = State()
#     waiting_part_input = State()  # expects repeated part entries
#     confirm_finish = State()
#
# class DeleteFilmStates(StatesGroup):
#     waiting_input = State()
#
# class BroadcastStates(StatesGroup):
#     waiting_content = State()
#
# class AddAdminStates(StatesGroup):
#     waiting_admin_id = State()
#     waiting_permissions = State()
#
# # Admin permission keys
# PERM = {
#     "ADD_FILM": "Add film",
#     "DELETE_FILM": "Delete film",
#     "CHANNELS": "Channels",
#     "USER_STAT": "User Statistic",
#     "FILM_STAT": "Film Statistic",
#     "ALL_WRITE": "All write",
#     "ADD_ADMIN": "Add admin",
# }
#
# async def is_admin(user_id: int) -> bool:
#     if user_id == ADMIN_ID:
#         return True
#     perms = await get_admin_permissions(user_id)
#     return perms is not None  # exists with some permissions
#
# async def has_perm(user_id: int, perm_key: str) -> bool:
#     if user_id == ADMIN_ID:
#         return True
#     perms = await get_admin_permissions(user_id)
#     return bool(perms and perm_key in perms)
#
# async def ensure_user_registered(msg: Message):
#     uid = msg.from_user.id
#     if not await user_exists(uid):
#         await add_user(uid)
#
# async def check_channels_gate(msg: Message) -> bool:
#     # Returns True if user can proceed
#     lst = await channels_list()
#     if not lst:
#         return True  # no channels defined -> free use
#
#     uid = msg.from_user.id
#     not_joined = []
#     for idx, ch in enumerate(lst, start=1):
#         ident = ch["id_or_username"]  # @username or channel ID
#         is_private = ch.get("is_private", False)
#         if is_private:
#             # Cannot reliably verify private membership; accept soft gate.
#             continue
#         try:
#             member = await bot.get_chat_member(chat_id=ident, user_id=uid)
#             status = member.status
#             if status not in ("member", "administrator", "creator"):
#                 not_joined.append((idx, ch))
#         except Exception:
#             # If we cannot check (invalid or private), treat as soft gate (no block)
#             continue
#
#     if not_joined:
#         kb = channels_inline_keyboard(await channels_list())
#         await msg.answer(
#             "Botdan to‘liq foydalanish uchun quyidagi kanallarga obuna bo‘ling, so‘ng Tekshirish tugmasini bosing.",
#             reply_markup=kb
#         )
#         return False
#     return True
#
# def format_top_films(items):
#     lines = []
#     for i, (title, views) in enumerate(items, start=1):
#         lines.append(f"{i}. {title} — {views} marta")
#     return "\n".join(lines) if lines else "Hozircha statistika mavjud emas."
#
# def format_user_stats(today, week, month, daily_views):
#     lines = [
#         f"• Bugun qo‘shilganlar: {today}",
#         f"• Oxirgi 7 kunda qo‘shilganlar: {week}",
#         f"• Oxirgi 30 kunda qo‘shilganlar: {month}",
#     ]
#     if daily_views:
#         lines.append("• Kunlik ko‘rishlar:")
#         for d, v in daily_views:
#             lines.append(f"   - {d}: {v}")
#     return "\n".join(lines)
#
# @dp.message(F.text == "/start")
# async def start_cmd(msg: Message, state: FSMContext):
#     await ensure_user_registered(msg)
#     if not await check_channels_gate(msg):
#         return
#     await msg.answer(
#         "Asosiy menyu",
#         reply_markup=user_main_menu()
#     )
#     logging.info(f"User {msg.from_user.id} pressed /start")
#
# @dp.message(F.text == "Kino qidirish")
# async def user_search(msg: Message, state: FSMContext):
#     await ensure_user_registered(msg)
#     if not await check_channels_gate(msg):
#         return
#     await msg.answer("Kod kiriting (masalan: GOT, LOTR_1):")
#     await state.set_state(SearchStates.waiting_code)
#
# @dp.message(SearchStates.waiting_code)
# async def handle_search_code(msg: Message, state: FSMContext):
#     code = msg.text.strip()
#     film = await get_film(code)
#     parts = await get_parts(code)
#     if not film and not parts:
#         await msg.answer("Bu kod bo‘yicha kino topilmadi.")
#         await state.clear()
#         return
#     if parts and len(parts) > 1:
#         await msg.answer("Qismni tanlang:", reply_markup=parts_selection_keyboard(parts))
#         await state.update_data(code=code)
#         await state.set_state(SearchStates.waiting_part_selection)
#     else:
#         # Single film or single part
#         part = parts[0] if parts else None
#         if part:
#             await increase_views(part["id"])
#             await msg.answer_video(video=part["video"], caption=part["title"] or film["title"])
#         else:
#             await msg.answer(film["title"] or "Kino", disable_web_page_preview=True)
#         await state.clear()
#
# @dp.callback_query(SearchStates.waiting_part_selection)
# async def handle_part_select(cb: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     code = data.get("code")
#     part_id = int(cb.data.split(":")[-1])  # e.g., "part:123"
#     part = await db_get_part_by_id(part_id)  # if you have it; else filter parts list
#     if not part:
#         await cb.answer("Qism topilmadi", show_alert=True)
#         return
#     await increase_views(part_id)
#     await cb.message.answer_video(video=part["video"], caption=part["title"])
#     await state.clear()
#     await cb.answer()
#
# @dp.message(F.text == "Kinolar statistikasi")
# async def user_top_films(msg: Message):
#     await ensure_user_registered(msg)
#     if not await check_channels_gate(msg):
#         return
#     items = await top_20_films_by_views()
#     text = format_top_films(items)
#     await msg.answer(text)
#
# @dp.message(F.text == "Adminga murojat")
# async def contact_admin(msg: Message):
#     await msg.answer("Adminga murojat uchun quyidagi havolaga bosing:\nhttps://t.me/kinovibe¬films_deb")
#
#
# # Show admin menu
# @dp.message(F.text == "Admin")
# async def admin_entry(msg: Message):
#     if not await is_admin(msg.from_user.id):
#         return await msg.answer("Sizda admin huquqi yo‘q.")
#     await msg.answer("Admin menyu", reply_markup=admin_main_menu())
#
#
# # Add film
# @dp.message(F.text == "Add film")
# async def admin_add_film(msg: Message, state: FSMContext):
#     if not await has_perm(msg.from_user.id, PERM["ADD_FILM"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     sample = (
#         "Kino qo‘shish namunasi:\n"
#         "1) Kod kiriting: GOT\n"
#         "2) Kino nomini kiriting: Game of Thrones\n"
#         "3) Yagona qismmi yoki bir nechta? (yagona/bir nechta)\n"
#         "Agar bir nechta bo‘lsa har bir qismni shunday kiriting:\n"
#         "film_code=GOT; title=S1E1; description=Pilot; video=<file_id or url>\n"
#         "Tayyor bo‘lgach 'finish' deb yozing."
#     )
#     await msg.answer(sample)
#     await msg.answer("Kod kiriting:")
#     await state.set_state(AddFilmStates.waiting_code)
#
#
# @dp.message(AddFilmStates.waiting_code)
# async def add_film_code(msg: Message, state: FSMContext):
#     await state.update_data(code=msg.text.strip())
#     await msg.answer("Kino nomini kiriting:")
#     await state.set_state(AddFilmStates.waiting_title)
#
#
# @dp.message(AddFilmStates.waiting_title)
# async def add_film_title(msg: Message, state: FSMContext):
#     await state.update_data(title=msg.text.strip())
#     await msg.answer("Yagona qismmi yoki bir nechta? (yagona/bir nechta)")
#     await state.set_state(AddFilmStates.waiting_single_or_parts)
#
#
# @dp.message(AddFilmStates.waiting_single_or_parts)
# async def add_film_mode(msg: Message, state: FSMContext):
#     mode = msg.text.strip().lower()
#     data = await state.get_data()
#     code, title = data["code"], data["title"]
#     await add_film(code, title)
#     if mode == "yagona":
#         await msg.answer("Video file_id yoki URL yuboring:")
#         await state.set_state(AddFilmStates.waiting_part_input)
#         await state.update_data(multi=False)
#     else:
#         await msg.answer(
#             "Har bir qismni quyidagi formatda yuboring:\nfilm_code=CODE; title=...; description=...; video=...\nTugagach 'finish' deb yozing.")
#         await state.set_state(AddFilmStates.waiting_part_input)
#         await state.update_data(multi=True)
#
#
# @dp.message(AddFilmStates.waiting_part_input, F.text.lower() == "finish")
# async def add_film_finish(msg: Message, state: FSMContext):
#     await state.clear()
#     await msg.answer("Kino qo‘shish yakunlandi ✅")
#     logging.info(f"Admin {msg.from_user.id} added film")
#
#
# @dp.message(AddFilmStates.waiting_part_input)
# async def add_film_part(msg: Message, state: FSMContext):
#     data = await state.get_data()
#     code = data.get("code")
#     multi = data.get("multi", False)
#     if multi:
#         try:
#             # Parse simple semicolon key=value format
#             text = msg.text
#             kv = {}
#             for seg in text.split(";"):
#                 k, v = seg.split("=", 1)
#                 kv[k.strip()] = v.strip()
#             await add_part(
#                 film_code=kv.get("film_code", code),
#                 title=kv["title"],
#                 description=kv.get("description", ""),
#                 video=kv["video"]
#             )
#             await msg.answer("Qism qo‘shildi. Davom ettiring yoki 'finish' deb yozing.")
#         except Exception as e:
#             await msg.answer(f"Format xato. Iltimos namunaga amal qiling.\nXato: {e}")
#     else:
#         # Single part using message content: video or text file_id
#         if msg.video and msg.video.file_id:
#             await add_part(film_code=code, title=data.get("title"), description="", video=msg.video.file_id)
#             await msg.answer("Video qo‘shildi. 'finish' deb yozing.")
#         else:
#             # Accept URL or file_id as text
#             await add_part(film_code=code, title=data.get("title"), description="", video=msg.text.strip())
#             await msg.answer("Video qo‘shildi. 'finish' deb yozing.")
#
#
# # Delete film
# @dp.message(F.text == "Delete film")
# async def admin_delete_film(msg: Message, state: FSMContext):
#     if not await has_perm(msg.from_user.id, PERM["DELETE_FILM"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     sample = (
#         "O‘chirish namunasi:\n"
#         "- Butun kino: code=GOT\n"
#         "- Yagona qism: part_id=123\n"
#         "Kerakli formatni kiriting."
#     )
#     await msg.answer(sample)
#     await state.set_state(DeleteFilmStates.waiting_input)
#
#
# @dp.message(DeleteFilmStates.waiting_input)
# async def handle_delete_input(msg: Message, state: FSMContext):
#     txt = msg.text.strip()
#     try:
#         if txt.startswith("code="):
#             code = txt.split("=", 1)[1].strip()
#             await delete_film(code=code)
#             await msg.answer("Kino o‘chirildi ✅")
#         elif txt.startswith("part_id="):
#             pid = int(txt.split("=", 1)[1])
#             await delete_film(part_id=pid)
#             await msg.answer("Qism o‘chirildi ✅")
#         else:
#             await msg.answer("Format noto‘g‘ri. 'code=...' yoki 'part_id=...' kiriting.")
#     except Exception as e:
#         await msg.answer(f"O‘chirishda xato: {e}")
#     await state.clear()
#
#
# # Channels management
# @dp.message(F.text == "Channels")
# async def admin_channels(msg: Message, state: FSMContext):
#     if not await has_perm(msg.from_user.id, PERM["CHANNELS"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     lst = await channels_list()
#     kb = channels_inline_keyboard(lst)
#     await msg.answer("Majburiy kanallar ro‘yxati (foydalanuvchi uchun ko‘rinishi):", reply_markup=kb)
#     await msg.answer(
#         "Admin amallari:\n- Qo‘shish: add @username yoki -1001234567890 (private id), private bo‘lsa 'private' so‘zini qo‘shing.\n- O‘chirish: del 2 (tartib raqami).")
#
#
# @dp.message(F.text.regexp(r"^add\s+"))
# async def admin_channels_add(msg: Message):
#     if not await has_perm(msg.from_user.id, PERM["CHANNELS"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     parts = msg.text.split()
#     try:
#         ident = parts[1]
#         is_private = (len(parts) > 2 and parts[2].lower() == "private")
#         await add_channel(ident, title=ident, is_private=is_private)
#         await msg.answer("Kanal qo‘shildi ✅")
#     except Exception as e:
#         await msg.answer(f"Qo‘shishda xato: {e}")
#
#
# @dp.message(F.text.regexp(r"^del\s+"))
# async def admin_channels_del(msg: Message):
#     if not await has_perm(msg.from_user.id, PERM["CHANNELS"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     try:
#         idx = int(msg.text.split()[1])
#         await remove_channel(idx)
#         await msg.answer("Kanal o‘chirildi ✅")
#     except Exception as e:
#         await msg.answer(f"O‘chirishda xato: {e}")
#
#
# # Verify button from channels list (for users)
# @dp.callback_query(F.data == "channels:verify")
# async def channels_verify(cb: CallbackQuery):
#     if await check_channels_gate(cb.message):
#         await cb.message.answer("Tekshirildi ✅ Endi botdan to‘liq foydalanishingiz mumkin.")
#     await cb.answer()
#
#
# # User Statistic
# @dp.message(F.text == "User Statistic")
# async def admin_user_stat(msg: Message):
#     if not await has_perm(msg.from_user.id, PERM["USER_STAT"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     today, week, month = await get_user_join_dates_stats()
#     daily_views = await get_daily_views_stats()
#     await msg.answer(format_user_stats(today, week, month, daily_views))
#
#
# # Film Statistic (paginated by 30)
# @dp.message(F.text == "Film Statistic")
# async def admin_film_stat(msg: Message):
#     if not await has_perm(msg.from_user.id, PERM["FILM_STAT"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     items, total = await list_films_paginated(page=1, page_size=30)
#     text = "\n".join([f"{i + 1}. {it['title']} — {it['code']}" for i, it in enumerate(items)]) or "Kinolar yo‘q."
#     kb = films_pagination_keyboard(current=1, total_count=total, page_size=30)
#     await msg.answer(text, reply_markup=kb)
#
#
# @dp.callback_query(F.data.startswith("films:page:"))
# async def films_page(cb: CallbackQuery):
#     _, _, p = cb.data.split(":")
#     page = int(p)
#     items, total = await list_films_paginated(page=page, page_size=30)
#     text = "\n".join(
#         [f"{(page - 1) * 30 + i + 1}. {it['title']} — {it['code']}" for i, it in enumerate(items)]) or "Kinolar yo‘q."
#     kb = films_pagination_keyboard(current=page, total_count=total, page_size=30)
#     await cb.message.edit_text(text, reply_markup=kb)
#     await cb.answer()
#
#
# # All write (broadcast to all users)
# @dp.message(F.text == "All write")
# async def admin_all_write(msg: Message, state: FSMContext):
#     if not await has_perm(msg.from_user.id, PERM["ALL_WRITE"]):
#         return await msg.answer("Bu amal uchun ruxsat yo‘q.")
#     await msg.answer("Barcha foydalanuvchilarga yuboriladigan kontentni yuboring (matn, rasm, video).")
#     await state.set_state(BroadcastStates.waiting_content)
#
#
# @dp.message(BroadcastStates.waiting_content)
# async def handle_broadcast(msg: Message, state: FSMContext):
#     users = await get_all_user_ids()
#     sent, fail = 0, 0
#     for uid in users:
#         try:
#             if msg.text:
#                 await bot.send_message(uid, msg.text)
#             elif msg.photo:
#                 await bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption or "")
#             elif msg.video:
#                 await bot.send_video(uid, msg.video.file_id, caption=msg.caption or "")
#             else:
#                 continue
#             sent += 1
#         except Exception:
#             fail += 1
#             continue
#     await save_broadcast_job(msg.from_user.id, len(users), sent, fail)
#     await state.clear()
#     await msg.answer(f"Yuborildi ✅ Jami: {len(users)}, muvaffaqiyatli: {sent}, xato: {fail}")
#
#
# # Add admin with permissions
# @dp.message(F.text == "Add admin")
# async def admin_add_admin(msg: Message, state: FSMContext):
#     if msg.from_user.id != ADMIN_ID:
#         return await msg.answer("Faqat bot egasi yangi admin qo‘sha oladi.")
#     sample = (
#         "Yangi admin qo‘shish:\n"
#         "1) Admin ID yuboring (masalan: 123456789)\n"
#         "2) Ruxsatlarni vergul bilan kiriting, masalan:\n"
#         "Add film, Delete film, Channels\n"
#         "Mavjud tugmalar: Add film, Delete film, Channels, User Statistic, Film Statistic, All write, Add admin"
#     )
#     await msg.answer(sample)
#     await msg.answer("Admin ID kiriting:")
#     await state.set_state(AddAdminStates.waiting_admin_id)
#
#
# @dp.message(AddAdminStates.waiting_admin_id)
# async def add_admin_id(msg: Message, state: FSMContext):
#     try:
#         aid = int(msg.text.strip())
#         await state.update_data(admin_id=aid)
#         await msg.answer("Ruxsatlarni kiriting (vergul bilan):")
#         await state.set_state(AddAdminStates.waiting_permissions)
#     except ValueError:
#         await msg.answer("ID noto‘g‘ri. Raqam kiriting.")
#
#
# @dp.message(AddAdminStates.waiting_permissions)
# async def add_admin_perms(msg: Message, state: FSMContext):
#     data = await state.get_data()
#     aid = data["admin_id"]
#     raw = [s.strip() for s in msg.text.split(",")]
#     # Map to valid keys
#     valid_names = set(PERM.values())
#     perms = [name for name in raw if name in valid_names]
#     if not perms:
#         return await msg.answer("Hech qanday to‘g‘ri ruxsat kiritilmadi. Qaytadan yuboring.")
#     await add_admin(aid)
#     await set_admin_permissions(aid, set(perms))
#     await state.clear()
#     await msg.answer(f"Yangi admin qo‘shildi ✅ ID={aid}\nRuxsatlar: {', '.join(perms)}")
#
# # Aiohttp app for webhook
# async def start_webhook():
#     await init_db()
#     await bot.set_webhook(f"{WEBHOOK_HOST}{WEBHOOK_PATH}")
#     app = web.Application()
#
#     # Aiogram webhook handler setup
#     from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
#     webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
#     webhook_handler.register(app, path=WEBHOOK_PATH)
#     setup_application(app, dp, bot=bot)
#
#     return app
#
# async def run_polling():
#     await bot.delete_webhook(drop_pending_updates=True)
#     await init_db()
#     await dp.start_polling(bot)
#
# if __name__ == "__main__":
#     if MODE.lower() == "polling":
#         logging.info("[INFO] Running in POLLING mode")
#         asyncio.run(run_polling())
#     else:
#         logging.info(f"[INFO] Running in WEBHOOK mode on port {PORT}, path={WEBHOOK_PATH}")
#         loop = asyncio.get_event_loop()
#         app = loop.run_until_complete(start_webhook())
#         web.run_app(app, port=PORT)

import sqlite3

conn = sqlite3.connect("films.db")
cur = conn.cursor()

# joined_at ustunini qo‘shamiz, default qiymatsiz
cur.execute("ALTER TABLE users ADD COLUMN joined_at TIMESTAMP;")
conn.commit()

# Eski foydalanuvchilarga vaqt qo‘yib chiqamiz
cur.execute("UPDATE users SET joined_at = CURRENT_TIMESTAMP WHERE joined_at IS NULL;")
conn.commit()

conn.close()
print("Migration done")
