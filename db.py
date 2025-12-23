import asyncpg
import os

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

async def get_conn():
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# ================= INIT =================
async def init_db():
    conn = await get_conn()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS films (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            title TEXT
        );
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id SERIAL PRIMARY KEY,
            movie_code TEXT,
            title TEXT,
            description TEXT,
            video TEXT,
            views INTEGER DEFAULT 0
        );
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        );
    """)
    await conn.close()

# ================= USERS =================
async def add_user(user_id: int):
    conn = await get_conn()
    await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
    await conn.close()

async def user_count():
    conn = await get_conn()
    count = await conn.fetchval("SELECT COUNT(*) FROM users")
    await conn.close()
    return count

# ================= FILMS =================
async def add_film(code, title):
    conn = await get_conn()
    await conn.execute("INSERT INTO films (code, title) VALUES ($1, $2)", code, title)
    await conn.close()

async def delete_film(code):
    conn = await get_conn()
    await conn.execute("DELETE FROM films WHERE code=$1", code)
    await conn.close()

async def get_film(code):
    conn = await get_conn()
    film = await conn.fetchrow("SELECT title FROM films WHERE code=$1", code)
    await conn.close()
    return film

async def film_count():
    conn = await get_conn()
    count = await conn.fetchval("SELECT COUNT(*) FROM films")
    await conn.close()
    return count

# ================= PARTS =================
async def add_part(movie_code, title, description, video):
    conn = await get_conn()
    await conn.execute(
        "INSERT INTO parts (movie_code, title, description, video) VALUES ($1, $2, $3, $4)",
        movie_code, title, description, video
    )
    await conn.close()

async def get_parts(movie_code):
    conn = await get_conn()
    parts = await conn.fetch("SELECT id, title, description, video, views FROM parts WHERE movie_code=$1 ORDER BY id", movie_code)
    await conn.close()
    return parts

async def increase_views(part_id):
    conn = await get_conn()
    await conn.execute("UPDATE parts SET views = views + 1 WHERE id=$1", part_id)
    await conn.close()
