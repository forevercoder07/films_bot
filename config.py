from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    BOT_TOKEN: str
    OWNER_ID: int
    DATABASE_URL: str
    LOG_FILE: str
    WEBHOOK_URL: str
    WEBHOOK_SECRET: str
    WEBAPP_HOST: str
    WEBAPP_PORT: int

def get_settings() -> Settings:
    return Settings(
        BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
        OWNER_ID=int(os.getenv("OWNER_ID", "0")),
        DATABASE_URL=os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/kino_db"),
        LOG_FILE=os.getenv("LOG_FILE", "/data/bot.log"),
        WEBHOOK_URL=os.getenv("WEBHOOK_URL", ""),
        WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET", "secret"),
        WEBAPP_HOST=os.getenv("WEBAPP_HOST", "0.0.0.0"),
        WEBAPP_PORT=int(os.getenv("WEBAPP_PORT", "8000")),
    )
