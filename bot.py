import logging
import asyncio
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Update

from config import get_settings
from logger import setup_logging
from db import init_db
from handlers import user_router, admin_router

# Konfiguratsiya va loglarni sozlash
settings = get_settings()
setup_logging(settings.LOG_FILE)

# Bot va dispatcher
bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
dp.include_router(user_router)
dp.include_router(admin_router)

# FastAPI app
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    # Bazani yaratish
    await init_db()
    # Webhookni sozlash
    await bot.set_webhook(
        url=settings.WEBHOOK_URL,
        secret_token=settings.WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    logging.info("Webhook set. Server started.")

@app.on_event("shutdown")
async def on_shutdown():
    try:
        # Webhookni o‘chirish
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        logging.warning(f"Webhook delete failed: {e}")
    # Aiogram sessionini yopish
    await bot.session.close()
    logging.info("Server stopped.")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Secret tokenni tekshirish
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# Render health-check uchun root endpoint
@app.get("/")
async def root():
    return {"status": "ok"}

# Qo‘shimcha health endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}
