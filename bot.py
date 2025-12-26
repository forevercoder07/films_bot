import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import BOT_TOKEN
from logger import logger
from db import engine, Base
from handlers import user_router, admin_router, channels_router

async def on_startup(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Boshlash"),
        BotCommand(command="admin", description="Admin menyu"),
        BotCommand(command="channels", description="Kanallar (tekshiruv)")
    ])
    logger.info("Bot commands set.")

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # DB init
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB tables created.")

    # Routers
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(channels_router)

    await on_startup(bot)
    logger.info("Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
