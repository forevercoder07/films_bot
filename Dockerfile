# Python 3.12.4 slim versiyasidan foydalanamiz
FROM python:3.12.4-slim

# Ishchi katalog
WORKDIR /app

# Talab qilinadigan kutubxonalarni nusxalash
COPY requirements.txt .

# Kutubxonalarni o'rnatish
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni konteynerga nusxalash
COPY . .

# Bot ishga tushganda main.py ishlaydi
CMD ["python", "main.py"]
