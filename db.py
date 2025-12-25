import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "films_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

pool = None

# -------------------------
# Init DB
# -------------------------
async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    async with pool.acquire() as conn:
        # Users
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Films
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS films (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Parts (video = Telegram file_id yoki URL saqlanadi)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id SERIAL PRIMARY KEY,
            film_code TEXT NOT NULL,
            title TEXT,
            description TEXT,
            video TEXT,
            views INTEGER DEFAULT 0
        )
        """)
        # Channels
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            id_or_username TEXT NOT NULL,
            title TEXT,
            is_private BOOLEAN DEFAULT FALSE
        )
        """)
        # Admins
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT UNIQUE,
            permissions TEXT
        )
        """)
        # Broadcast jobs
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_jobs (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT,
            total_users INTEGER,
            sent INTEGER,
            failed INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

# -------------------------
# Users
# -------------------------
async def add_user(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )

async def user_exists(user_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM users WHERE user_id=$1", user_id)
        return row is not None

async def get_all_user_ids():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]

# -------------------------
# Films
# -------------------------
async def add_film(code: str, title: str, description: str = ""):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO films (code, title, description) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            code, title, description
        )

async def get_film(code: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT code, title, description FROM films WHERE code=$1", code)
        return dict(row) if row else None

async def list_films_paginated(page: int, page_size: int):
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT code, title FROM films ORDER BY id DESC LIMIT $1 OFFSET $2", page_size, offset)
        total = await conn.fetchval("SELECT COUNT(*) FROM films")
        return [dict(r) for r in rows], total

async def delete_film(code: str = None, part_id: int = None):
    async with pool.acquire() as conn:
        if code:
            await conn.execute("DELETE FROM films WHERE code=$1", code)
            await conn.execute("DELETE FROM parts WHERE film_code=$1", code)
        elif part_id:
            await conn.execute("DELETE FROM parts WHERE id=$1", part_id)

# -------------------------
# Parts
# -------------------------
async def add_part(film_code: str, title: str, description: str, video: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO parts (film_code, title, description, video) VALUES ($1, $2, $3, $4)",
            film_code, title, description, video
        )

async def get_parts(code: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM parts WHERE film_code=$1", code)
        return [dict(r) for r in rows]

async def db_get_part_by_id(part_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM parts WHERE id=$1", part_id)
        return dict(row) if row else None

async def increase_views(part_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE parts SET views = views + 1 WHERE id=$1", part_id)

async def top_20_films_by_views():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT f.title, COALESCE(SUM(p.views),0) as total_views
        FROM films f
        LEFT JOIN parts p ON f.code = p.film_code
        GROUP BY f.code, f.title
        ORDER BY total_views DESC
        LIMIT 20
        """)
        return [(r["title"], r["total_views"]) for r in rows]

# -------------------------
# Channels
# -------------------------
async def channels_list():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM channels")
        return [dict(r) for r in rows]

async def add_channel(ident: str, title: str = None, is_private: bool = False):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO channels (id_or_username, title, is_private) VALUES ($1, $2, $3)",
            ident.strip(), title or ident.strip(), is_private
        )

async def remove_channel(idx: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM channels WHERE id=$1", idx)

# -------------------------
# Admins
# -------------------------
async def add_admin(admin_id: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO admins (admin_id) VALUES ($1) ON CONFLICT DO NOTHING", admin_id)

async def set_admin_permissions(admin_id: int, perms: set):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE admins SET permissions=$1 WHERE admin_id=$2", ",".join(perms), admin_id)

async def get_admin_permissions(admin_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT permissions FROM admins WHERE admin_id=$1", admin_id)
        return set(row["permissions"].split(",")) if row and row["permissions"] else set()

# -------------------------
# Broadcast jobs
# -------------------------
async def save_broadcast_job(admin_id: int, total: int, sent: int, fail: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO broadcast_jobs (admin_id, total_users, sent, failed) VALUES ($1, $2, $3, $4)",
            admin_id, total, sent, fail
        )

# Statistics
async def get_user_join_dates_stats():
    async with pool.acquire() as conn:
        today = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE DATE(joined_at) = CURRENT_DATE"
        )
        week = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE joined_at >= CURRENT_DATE - INTERVAL '7 days'"
        )
        month = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE joined_at >= CURRENT_DATE - INTERVAL '30 days'"
        )
        return today, week, month

async def get_daily_views_stats(days: int = 7):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT DATE(created_at) as d, COUNT(*) as v
        FROM films
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY d ORDER BY d DESC
        """)
        return [(r["d"], r["v"]) for r in rows]
