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

settings = get_settings()
setup_logging(settings.LOG_FILE)

bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
dp.include_router(user_router)
dp.include_router(admin_router)

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await init_db()
    # Webhook ni sozlash: secret token bilan
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
        # Webhookni o‘chirib qo‘yish
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        logging.warning(f"Webhook delete failed: {e}")
    # Aiogram ichki sessionini yopish
    await bot.session.close()
    logging.info("Server stopped.")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Secret tokenni tekshiramiz
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status": "ok"}
