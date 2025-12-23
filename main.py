import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from db import *
from keyboards import *
from states import *

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", 8443))

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ========== STARTUP / SHUTDOWN ==========
async def on_startup(app):
    await init_db()
    await bot.set_webhook(WEBHOOK_URL)
    print(f"[INFO] Webhook set: {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.session.close()
    print("[INFO] Bot closed")

# ========== /START ==========
@dp.message(F.text == "/start")
async def start(msg: Message):
    await add_user(msg.from_user.id)
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("👮 Admin panel", reply_markup=admin_kb)
    else:
        await msg.answer("🎬 Kino botga xush kelibsiz", reply_markup=user_kb)

# ========== USER PANEL ==========
@dp.message(F.text == "🎬 Kino topish")
async def ask_code(msg: Message):
    await msg.answer("🎞 Kino kodini kiriting:")

@dp.message(F.text.regexp(r"^\d+$"))
async def get_film_by_code(msg: Message):
    film = await get_film(msg.text)
    if not film:
        await msg.answer("❌ Bunday kino yo‘q")
        return
    parts = await get_parts(msg.text)
    if not parts:
        await msg.answer(f"🎬 {film['title']}\nHozircha qismlar yo‘q.")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{p['title']} ({p['views']} marta)", callback_data=f"part_{p['id']}")] for p in parts
        ]
    )
    await msg.answer(f"🎬 {film['title']}\nQismlardan birini tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("part_"))
async def send_part(call: CallbackQuery):
    part_id = int(call.data.split("_")[1])
    # partni olish
    parts = await get_parts('')
    part = next((p for p in parts if p['id'] == part_id), None)
    if not part:
        await call.message.answer("❌ Qism topilmadi")
        await call.answer()
        return
    await increase_views(part_id)
    await call.message.answer_video(part['video'], caption=f"{part['title']}\n{part['description']}\n👁 {part['views']+1} marta")
    await call.answer()

@dp.message(F.text == "📊 Statistikalar")
async def stats_user(msg: Message):
    count = await film_count()
    users = await user_count()
    await msg.answer(f"🎞 Kinolar soni: {count}\n👥 Foydalanuvchilar: {users}")

@dp.message(F.text == "📩 Adminga murojaat")
async def contact_admin(msg: Message):
    await bot.send_message(ADMIN_ID, f"📩 Foydalanuvchi {msg.from_user.id} murojaat qilmoqda")
    await msg.answer("✅ Sizning xabaringiz adminga yuborildi")

# ========== ADMIN PANEL ==========
@dp.message(F.text == "➕ Kino qo'shish")
async def add_film_start(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("🎬 Kino kodini kiriting:")
    await state.set_state(AddFilm.code)

@dp.message(AddFilm.code)
async def add_film_code(msg: Message, state: FSMContext):
    await state.update_data(code=msg.text)
    await msg.answer("🎬 Kino nomini kiriting:")
    await state.set_state(AddFilm.title)

@dp.message(AddFilm.title)
async def add_film_title(msg: Message, state: FSMContext):
    data = await state.get_data()
    await add_film(data["code"], msg.text)
    await msg.answer("✅ Kino qo‘shildi", reply_markup=admin_kb)
    await state.clear()

@dp.message(F.text == "🗑 Kino o'chirish")
async def delete_film_start(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("❌ O‘chiriladigan kino kodini kiriting:")
    await state.set_state(DeleteFilm.code)

@dp.message(DeleteFilm.code)
async def delete_film_msg(msg: Message, state: FSMContext):
    await delete_film(msg.text)
    await msg.answer("🗑 Kino o‘chirildi", reply_markup=admin_kb)
    await state.clear()

@dp.message(F.text == "➕ Kino qism qo'shish")
async def add_part_start(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("🎬 Kino kodi:")
    await state.set_state(AddPart.movie_code)

@dp.message(AddPart.movie_code)
async def add_part_code(msg: Message, state: FSMContext):
    await state.update_data(movie_code=msg.text)
    await msg.answer("🎬 Qism nomi:")
    await state.set_state(AddPart.title)

@dp.message(AddPart.title)
async def add_part_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text)
    await msg.answer("📄 Qism tavsifi:")
    await state.set_state(AddPart.description)

@dp.message(AddPart.description)
async def add_part_desc(msg: Message, state: FSMContext):
    await state.update_data(description=msg.text)
    await msg.answer("🎥 Video file_id:")
    await state.set_state(AddPart.video)

@dp.message(AddPart.video)
async def add_part_video(msg: Message, state: FSMContext):
    data = await state.get_data()
    await add_part(data["movie_code"], data["title"], data["description"], msg.text)
    await msg.answer("✅ Qism qo‘shildi", reply_markup=admin_kb)
    await state.clear()

@dp.message(F.text == "📊 User statistikasi")
async def admin_users(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    count = await user_count()
    await msg.answer(f"👥 Userlar: {count}")

@dp.message(F.text == "🎞 Kino statistikasi")
async def admin_films(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    count = await film_count()
    await msg.answer(f"🎬 Kinolar: {count}")

@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("📢 Yuboriladigan xabarni yozing:")
    await state.set_state(Broadcast.message)

@dp.message(Broadcast.message)
async def broadcast_send(msg: Message, state: FSMContext):
    conn = await get_conn()
    users = await conn.fetch("SELECT user_id FROM users")
    for u in users:
        try:
            await bot.send_message(u['user_id'], msg.text)
        except: continue
    await msg.answer("✅ Xabar barcha userlarga yuborildi")
    await state.clear()

@dp.message(F.text == "🔙 Asosiy menyu")
async def back(msg: Message):
    await start(msg)

# ========== WEBHOOK APP ==========
async def start_webhook():
    logging.basicConfig(level=logging.INFO)

    # DB ulanishini yaratamiz
    await init_db()

    # Webhook URL ni botga o‘rnatamiz
    await bot.set_webhook(f"{WEBHOOK_HOST}{WEBHOOK_PATH}")

    # aiohttp app yaratamiz
    app = web.Application()

    # Aiogram dispatcher’ni aiohttp serverga ulash
    app.router.add_post(WEBHOOK_PATH, dp.start_webhook)

    # Shutdown event
    async def on_shutdown(app: web.Application):
        await bot.delete_webhook()
        await bot.session.close()
        await db_pool.close()

    app.on_shutdown.append(on_shutdown)

    # Serverni ishga tushiramiz
    web.run_app(app, port=PORT)

if __name__ == "__main__":
    app = asyncio.run(start_webhook())
    web.run_app(app, port=PORT)         # event loopni web.run_app o‘zi boshqaradi
