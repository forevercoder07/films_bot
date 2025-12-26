from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, BigInteger, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, select, func, delete
from datetime import datetime, timedelta
from typing import Optional, Sequence
from config import DATABASE_URL

class Base(DeclarativeBase):
    pass

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Models
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # tg user id
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Admin(Base):
    __tablename__ = "admins"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permissions: Mapped[str] = mapped_column(Text, default="")  # comma-separated keys

class Film(Base):
    __tablename__ = "films"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    parts: Mapped[list["FilmPart"]] = relationship(back_populates="film", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("code", name="uq_films_code"),)

class FilmPart(Base):
    __tablename__ = "film_parts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id", ondelete="CASCADE"))
    part_number: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[str] = mapped_column(Text)
    views: Mapped[int] = mapped_column(Integer, default=0)
    film: Mapped[Film] = relationship(back_populates="parts")
    __table_args__ = (UniqueConstraint("film_id", "part_number", name="uq_film_part"),)

class ViewLog(Base):
    __tablename__ = "view_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    film_id: Mapped[int] = mapped_column(Integer)
    part_id: Mapped[int] = mapped_column(Integer)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ChannelRule(Base):
    __tablename__ = "channel_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    chat_id: Mapped[str] = mapped_column(String(64))  # @username yoki -100...
    invite_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True)

# CRUD helpers
async def ensure_user(user_id: int):
    async with SessionLocal() as s:
        u = await s.get(User, user_id)
        if not u:
            s.add(User(id=user_id))
            await s.commit()

async def get_admin(user_id: int) -> Optional[Admin]:
    async with SessionLocal() as s:
        return await s.get(Admin, user_id)

async def add_admin(user_id: int, permissions: str):
    async with SessionLocal() as s:
        s.add(Admin(user_id=user_id, permissions=permissions))
        await s.commit()

async def all_admins() -> Sequence[Admin]:
    async with SessionLocal() as s:
        res = await s.execute(select(Admin))
        return res.scalars().all()

async def add_channel(title: str, chat_id: str, invite_link: Optional[str], is_private: bool, required: bool):
    async with SessionLocal() as s:
        s.add(ChannelRule(title=title, chat_id=chat_id, invite_link=invite_link, is_private=is_private, required=required))
        await s.commit()

async def get_channels() -> Sequence[ChannelRule]:
    async with SessionLocal() as s:
        res = await s.execute(select(ChannelRule).order_by(ChannelRule.id.asc()))
        return res.scalars().all()

async def delete_channel(rule_id: int) -> bool:
    async with SessionLocal() as s:
        res = await s.execute(delete(ChannelRule).where(ChannelRule.id == rule_id))
        await s.commit()
        return res.rowcount > 0

async def add_film(code: str, title: str) -> Film:
    async with SessionLocal() as s:
        film = Film(code=code, title=title)
        s.add(film)
        await s.commit()
        await s.refresh(film)
        return film

async def get_film_by_code(code: str) -> Optional[Film]:
    async with SessionLocal() as s:
        res = await s.execute(select(Film).where(Film.code == code))
        return res.scalars().first()

async def add_film_part_db(film_id: int, part_number: int, file_id: str) -> FilmPart:
    async with SessionLocal() as s:
        part = FilmPart(film_id=film_id, part_number=part_number, file_id=file_id)
        s.add(part)
        await s.commit()
        await s.refresh(part)
        return part

async def delete_film_by_code(code: str) -> bool:
    async with SessionLocal() as s:
        film = await s.scalar(select(Film).where(Film.code == code))
        if not film:
            return False
        await s.delete(film)
        await s.commit()
        return True

async def delete_film_part(code: str, part_number: int) -> bool:
    async with SessionLocal() as s:
        q = select(FilmPart).join(Film).where(Film.code == code, FilmPart.part_number == part_number)
        res = await s.execute(q)
        part = res.scalars().first()
        if not part:
            return False
        await s.delete(part)
        await s.commit()
        return True

async def film_parts_by_code(code: str) -> Sequence[FilmPart]:
    async with SessionLocal() as s:
        res = await s.execute(select(FilmPart).join(Film).where(Film.code == code).order_by(FilmPart.part_number.asc()))
        return res.scalars().all()

async def inc_view(film_id: int, part_id: int, user_id: int):
    async with SessionLocal() as s:
        part = await s.get(FilmPart, part_id)
        if part:
            part.views += 1
            film = await s.get(Film, film_id)
            if film:
                film.total_views += 1
        s.add(ViewLog(user_id=user_id, film_id=film_id, part_id=part_id))
        await s.commit()

async def top20_films():
    async with SessionLocal() as s:
        res = await s.execute(
            select(Film.title, Film.total_views)
            .order_by(Film.total_views.desc())
            .limit(20)
        )
        return res.all()

async def user_counts():
    async with SessionLocal() as s:
        total = await s.scalar(select(func.count(User.id)))
        now = datetime.utcnow()
        day_start = now - timedelta(days=1)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        daily = await s.scalar(select(func.count(User.id)).where(User.joined_at >= day_start))
        weekly = await s.scalar(select(func.count(User.id)).where(User.joined_at >= week_start))
        monthly = await s.scalar(select(func.count(User.id)).where(User.joined_at >= month_start))
        daily_views = await s.scalar(select(func.count(ViewLog.id)).where(ViewLog.viewed_at >= day_start))
        return total or 0, daily or 0, weekly or 0, monthly or 0, daily_views or 0

async def film_catalog_paginated(offset: int, limit: int = 30):
    async with SessionLocal() as s:
        res = await s.execute(select(Film).order_by(Film.title.asc()).offset(offset).limit(limit))
        return res.scalars().all()
