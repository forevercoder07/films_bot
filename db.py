from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Text, Boolean, ForeignKey, func, select
)
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship

from config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Film(Base):
    __tablename__ = "films"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    video_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    parts: Mapped[List["FilmPart"]] = relationship(back_populates="film", cascade="all, delete-orphan")

class FilmPart(Base):
    __tablename__ = "film_parts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))  # e.g. "1-qism"
    description: Mapped[str] = mapped_column(Text, default="")
    video_file_id: Mapped[str] = mapped_column(String(512))
    film: Mapped[Film] = relationship(back_populates="parts")

class ViewLog(Base):
    __tablename__ = "view_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    film_code: Mapped[str] = mapped_column(String(64), index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    part_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    link: Mapped[str] = mapped_column(String(512))  # @username or invite link
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=1)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # qat’iy tekshiruv uchun

class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_access: Mapped[bool] = mapped_column(Boolean, default=False)
    can_add_film: Mapped[bool] = mapped_column(Boolean, default=False)
    can_add_parts: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_film: Mapped[bool] = mapped_column(Boolean, default=False)
    can_channels: Mapped[bool] = mapped_column(Boolean, default=False)
    can_user_stat: Mapped[bool] = mapped_column(Boolean, default=False)
    can_film_stat: Mapped[bool] = mapped_column(Boolean, default=False)
    can_all_write: Mapped[bool] = mapped_column(Boolean, default=False)
    can_add_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    can_admin_stat: Mapped[bool] = mapped_column(Boolean, default=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Users
async def ensure_user(tg_id: int) -> None:
    async with SessionLocal() as s:
        exists = await s.scalar(select(User).where(User.tg_id == tg_id))
        if not exists:
            s.add(User(tg_id=tg_id))
            await s.commit()

# Films
async def add_film(code: str, title: str, description: str, video_file_id: Optional[str]) -> Tuple[bool, str]:
    async with SessionLocal() as s:
        exists = await s.scalar(select(Film).where(Film.code == code))
        if exists:
            return False, "Bu kod bilan film mavjud."
        s.add(Film(code=code, title=title, description=description, video_file_id=video_file_id))
        await s.commit()
        return True, "Film qo‘shildi."

async def get_film_by_code(code: str) -> Optional[Film]:
    async with SessionLocal() as s:
        return await s.scalar(select(Film).where(Film.code == code))

async def add_part(code: str, name: str, description: str, video_file_id: str) -> Tuple[bool, str]:
    async with SessionLocal() as s:
        film = await s.scalar(select(Film).where(Film.code == code))
        if not film:
            return False, "Kod bo‘yicha film topilmadi."
        dup = await s.scalar(select(FilmPart).where(FilmPart.film_id == film.id, FilmPart.name == name))
        if dup:
            return False, "Bu nomdagi qism mavjud."
        s.add(FilmPart(film_id=film.id, name=name, description=description, video_file_id=video_file_id))
        await s.commit()
        return True, "Qism qo‘shildi."

async def delete_film_or_part(code: str, part_name: Optional[str]) -> Tuple[bool, str]:
    async with SessionLocal() as s:
        film = await s.scalar(select(Film).where(Film.code == code))
        if not film:
            return False, "Film topilmadi."
        if part_name:
            part = await s.scalar(select(FilmPart).where(FilmPart.film_id == film.id, FilmPart.name == part_name))
            if not part:
                return False, "Qism topilmadi."
            await s.delete(part)
            await s.commit()
            return True, "Qism o‘chirildi."
        else:
            await s.delete(film)
            await s.commit()
            return True, "Film to‘liq o‘chirildi."

async def list_parts(code: str) -> List[FilmPart]:
    async with SessionLocal() as s:
        film = await s.scalar(select(Film).where(Film.code == code))
        if not film:
            return []
        res = await s.scalars(select(FilmPart).where(FilmPart.film_id == film.id).order_by(FilmPart.name))
        return list(res)

async def log_view(code: str, tg_id: int, part_name: Optional[str]) -> None:
    async with SessionLocal() as s:
        s.add(ViewLog(film_code=code, tg_id=tg_id, part_name=part_name))
        await s.commit()

async def top_films(limit: int = 20) -> List[Tuple[str, str, int]]:
    async with SessionLocal() as s:
        stmt = (
            select(ViewLog.film_code, func.coalesce(Film.title, ViewLog.film_code), func.count(ViewLog.id))
            .join(Film, Film.code == ViewLog.film_code, isouter=True)
            .group_by(ViewLog.film_code, Film.title)
            .order_by(func.count(ViewLog.id).desc())
            .limit(limit)
        )
        rows = await s.execute(stmt)
        return [(r[0], r[1], r[2]) for r in rows.all()]

async def user_stats() -> Tuple[int, int, int, int, int]:
    async with SessionLocal() as s:
        total = await s.scalar(select(func.count(User.id)))
        today = date.today()
        today_count = await s.scalar(select(func.count(User.id)).where(func.date(User.joined_at) == today))
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_count = await s.scalar(select(func.count(User.id)).where(User.joined_at >= week_ago))
        month_ago = datetime.utcnow() - timedelta(days=30)
        month_count = await s.scalar(select(func.count(User.id)).where(User.joined_at >= month_ago))
        today_views = await s.scalar(select(func.count(ViewLog.id)).where(func.date(ViewLog.viewed_at) == today))
        return total or 0, today_count or 0, week_count or 0, month_count or 0, today_views or 0

async def list_films_paginated(offset: int, limit: int) -> List[Film]:
    async with SessionLocal() as s:
        res = await s.scalars(select(Film).order_by(Film.title).offset(offset).limit(limit))
        return list(res)

async def films_count() -> int:
    async with SessionLocal() as s:
        return await s.scalar(select(func.count(Film.id))) or 0

# Channels CRUD
async def add_channel(title: str, link: str, is_private: bool, order: int, chat_id: Optional[int]) -> Tuple[bool, str]:
    async with SessionLocal() as s:
        s.add(Channel(title=title, link=link, is_private=is_private, order=order, chat_id=chat_id))
        await s.commit()
        return True, "Kanal qo‘shildi."

async def del_channel(order: int) -> Tuple[bool, str]:
    async with SessionLocal() as s:
        ch = await s.scalar(select(Channel).where(Channel.order == order))
        if not ch:
            return False, "Bu tartib raqamli kanal topilmadi."
        await s.delete(ch)
        await s.commit()
        return True, "Kanal o‘chirildi."

async def list_channels() -> List[Channel]:
    async with SessionLocal() as s:
        res = await s.scalars(select(Channel).order_by(Channel.order))
        return list(res)

# Admins
async def is_owner(tg_id: int) -> bool:
    return tg_id == settings.OWNER_ID

async def get_admin(tg_id: int) -> Optional[Admin]:
    async with SessionLocal() as s:
        return await s.scalar(select(Admin).where(Admin.tg_id == tg_id))

async def add_admin_with_permissions(tg_id: int, full_access: bool, perms: dict) -> Tuple[bool, str]:
    async with SessionLocal() as s:
        exists = await s.scalar(select(Admin).where(Admin.tg_id == tg_id))
        if exists:
            return False, "Bu admin allaqachon mavjud."
        admin = Admin(
            tg_id=tg_id,
            full_access=full_access,
            can_add_film=perms.get("add_film", False),
            can_add_parts=perms.get("add_parts", False),
            can_delete_film=perms.get("delete_film", False),
            can_channels=perms.get("channels", False),
            can_user_stat=perms.get("user_stat", False),
            can_film_stat=perms.get("film_stat", False),
            can_all_write=perms.get("all_write", False),
            can_add_admin=perms.get("add_admin", False),
            can_admin_stat=perms.get("admin_stat", False),
        )
        s.add(admin)
        await s.commit()
        return True, "Admin qo‘shildi."

async def list_admins() -> List[Admin]:
    async with SessionLocal() as s:
        res = await s.scalars(select(Admin).order_by(Admin.id))
        return list(res)
