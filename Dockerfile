# Python bazasi
FROM python:3.12-slim

# Ishchi katalog
WORKDIR /app

# Kutubxonalar uchun requirements.txt faylini nusxalash
COPY requirements.txt .

# Kutubxonalarni o‘rnatish
RUN pip install --no-cache-dir -r requirements.txt

# Butun kodni konteynerga nusxalash
COPY . .

# Environment variables (BOT_TOKEN, ADMIN_ID va boshqalar) serverda beriladi
# Misol: docker run -e BOT_TOKEN=xxx -e ADMIN_ID=123 ...

# Botni ishga tushirish
CMD ["python", "main.py"]
