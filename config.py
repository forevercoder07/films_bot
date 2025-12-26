import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

if not BOT_TOKEN or not DATABASE_URL:
    raise RuntimeError("BOT_TOKEN yoki DATABASE_URL .env da ko‘rsatilmagan.")
