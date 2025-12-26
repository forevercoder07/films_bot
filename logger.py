import logging
from logging.handlers import RotatingFileHandler
import os
from config import LOG_LEVEL

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("kino_bot")
logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
fh = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
fh.setFormatter(fmt)
ch = logging.StreamHandler()
ch.setFormatter(fmt)

logger.addHandler(fh)
logger.addHandler(ch)
