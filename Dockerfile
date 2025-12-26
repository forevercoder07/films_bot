FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# Loglar uchun katalog
RUN mkdir -p /app/logs

# Healthcheck (ixtiyoriy)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD [ "bash", "-c", "test -f /app/logs/bot.log" ]

CMD ["python", "src/bot.py"]
