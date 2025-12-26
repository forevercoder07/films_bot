FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Kerakli build tools
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Kutubxonalarni o‘rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyihani nusxalash
COPY . .

# Loglar uchun katalog
RUN mkdir -p /app/logs

# Render portni ko‘rishi uchun dummy server
EXPOSE 8000

# Botni va dummy serverni birga ishga tushirish
CMD ["sh", "-c", "python bot.py & uvicorn dummy:app --host 0.0.0.0 --port 8000"]
