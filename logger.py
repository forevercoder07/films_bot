# logger.py
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_file: str | None = None):
    """
    Railway uchun optimallashtirilgan logging.
    - Default: faqat console (stdout)
    - Agar log_file berilsa: /tmp katalogida fayl yaratadi
    """

    handlers = [logging.StreamHandler()]  # console handler

    if log_file:
        # Railway ephemeral storage uchun /tmp katalogidan foydalanamiz
        if not log_file.startswith("/tmp/"):
            log_file = "/tmp/bot.log"

        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8"
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
