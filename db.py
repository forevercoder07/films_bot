import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")  # Masalan: postgres://user:password@localhost:5432/dbname

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DB_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS films (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            title TEXT
        );
        CREATE TABLE IF NOT EXISTS parts (
            id SERIAL PRIMARY KEY,
            film_code TEXT,
            title TEXT,
            description TEXT,
            video TEXT,
            views INT DEFAULT 0
        );
        """)

async def get_conn():
    return db_pool

async def add_user(user_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id) VALUES ($1)
        ON CONFLICT (user_id) DO NOTHING
        """, user_id)

async def user_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

async def add_film(code: str, title: str):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO films (code, title) VALUES ($1, $2)
        ON CONFLICT (code) DO NOTHING
        """, code, title)

async def delete_film(code: str):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM films WHERE code = $1", code)
        await conn.execute("DELETE FROM parts WHERE film_code = $1", code)

async def film_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM films")

async def get_film(code: str):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM films WHERE code = $1", code)

async def add_part(film_code: str, title: str, description: str, video: str):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO parts (film_code, title, description, video) VALUES ($1, $2, $3, $4)
        """, film_code, title, description, video)

async def get_parts(film_code: str):
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM parts WHERE film_code = $1", film_code)

async def get_part_by_id(part_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM parts WHERE id = $1", part_id)

async def increase_views(part_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE parts SET views = views + 1 WHERE id = $1", part_id)
