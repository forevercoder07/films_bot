import aiosqlite

DB_PATH = "films.db"

# ===== Database init =====
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Users jadvali — joined_at ustuni qo‘shilgan
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Films jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Parts jadvali

        await db.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_code TEXT NOT NULL,
            title TEXT,
            description TEXT,
            video TEXT,
            views INTEGER DEFAULT 0,
            FOREIGN KEY(film_code) REFERENCES films(code) ON DELETE CASCADE
        )
        """)



        # Channels jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_or_username TEXT NOT NULL,
            title TEXT,
            is_private INTEGER DEFAULT 0
        )
        """)


        # Admins jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER UNIQUE,
            permissions TEXT
        )
        """)

        # Broadcast jobs jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            total_users INTEGER,
            sent INTEGER,
            failed INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.commit()

# ===== Users =====
async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, joined_at) VALUES (?, CURRENT_TIMESTAMP)",
            (user_id,)
        )
        await db.commit()


async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone() is not None

async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT admin_id FROM admins")
        rows = await cur.fetchall()
        return [{"admin_id": r[0]} for r in rows]

# ===== Films =====
async def add_film(code: str, title: str, description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO films (code, title, description) VALUES (?, ?, ?)",
            (code, title, description)
        )
        await db.commit()

async def get_film(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT code, title, description FROM films WHERE code = ?", (code,))
        row = await cur.fetchone()
        return {"code": row[0], "title": row[1], "description": row[2]} if row else None

async def list_films_paginated(page: int, page_size: int):
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT code, title FROM films ORDER BY id DESC LIMIT ? OFFSET ?", (page_size, offset))
        items = await cur.fetchall()
        cur2 = await db.execute("SELECT COUNT(*) FROM films")
        total = (await cur2.fetchone())[0]
        return [{"code": r[0], "title": r[1]} for r in items], total

async def top_20_films_by_views():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT f.title, SUM(p.views) as total_views
        FROM films f
        LEFT JOIN parts p ON f.code = p.film_code
        GROUP BY f.code
        ORDER BY total_views DESC
        LIMIT 20
        """)
        rows = await cur.fetchall()
        # title, views (views None bo'lsa 0 qilib beramiz)
        return [(r[0], r[1] if r[1] is not None else 0) for r in rows]


async def delete_film(code: str = None, part_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if code:
            # butun filmni o‘chirish
            await db.execute("DELETE FROM films WHERE code = ?", (code,))
            await db.execute("DELETE FROM parts WHERE film_code = ?", (code,))
        elif part_id:
            # faqat bitta qismni o‘chirish
            await db.execute("DELETE FROM parts WHERE id = ?", (part_id,))
        await db.commit()



async def add_part(film_code: str, title: str, description: str, video: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO parts (film_code, title, description, video) VALUES (?, ?, ?, ?)",
            (film_code, title, description, video)
        )
        await db.commit()

async def get_parts(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM parts WHERE film_code = ?", (code,))
        rows = await cur.fetchall()
        return [dict(zip([c[0] for c in cur.description], r)) for r in rows]

async def db_get_part_by_id(part_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
        row = await cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None

async def increase_views(part_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE parts SET views = views + 1 WHERE id = ?", (part_id,))
        await db.commit()



# ===== Channels =====
async def channels_list():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM channels")
        rows = await cur.fetchall()
        return [dict(zip([c[0] for c in cur.description], r)) for r in rows]

async def add_channel(ident: str, title: str = None, is_private: bool = False):
    """
    Kanal qo'shish:
    - ident: '@username' yoki kanal ID (majburiy, bo'sh bo'lishi mumkin emas)
    - title: kanal nomi (agar berilmasa ident ishlatiladi)
    - is_private: True bo'lsa private kanal sifatida saqlanadi
    """
    if not ident or not ident.strip():
        raise ValueError("Kanal identifikatori bo'sh bo'lishi mumkin emas")

    ident = ident.strip()
    if not title:
        title = ident

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO channels (id_or_username, title, is_private) VALUES (?, ?, ?)",
            (ident, title, int(is_private))
        )
        await db.commit()


async def remove_channel(idx: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE id = ?", (idx,))
        await db.commit()

# ===== Statistikalar =====
async def get_user_join_dates_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        # Bugun qo‘shilganlar
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at) = date('now')"
        )
        today = (await cur.fetchone())[0]

        # Oxirgi 7 kun
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at >= datetime('now','-7 days')"
        )
        week = (await cur.fetchone())[0]

        # Oxirgi 30 kun
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at >= datetime('now','-30 days')"
        )
        month = (await cur.fetchone())[0]

        return today, week, month


async def get_daily_views_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT date(joined_at) as d, COUNT(*) as v
        FROM users
        GROUP BY date(joined_at)
        ORDER BY d DESC
        LIMIT 10
        """)
        return await cur.fetchall()

# ===== Broadcast jobs =====
async def save_broadcast_job(admin_id: int, total: int, sent: int, fail: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO broadcast_jobs (admin_id, total_users, sent, failed) VALUES (?, ?, ?, ?)",
            (admin_id, total, sent, fail)
        )
        await db.commit()

# ===== Admins =====
async def add_admin(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (admin_id,))
        await db.commit()

async def set_admin_permissions(admin_id: int, perms: set):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET permissions = ? WHERE admin_id = ?", (",".join(perms), admin_id))
        await db.commit()

async def get_admin_permissions(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT permissions FROM admins WHERE admin_id = ?", (admin_id,))
        row = await cur.fetchone()
        if row and row[0]:
            return set(row[0].split(","))
        return set()
