"""
database.py
===========
- Creates the async SQLAlchemy engine
- Defines all 5 tables as Python classes (ORM models)
- Creates tables automatically on startup — no manual SQL needed
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, Enum as SAEnum, Text
)
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DB_URL", "mysql+aiomysql://root:password@localhost:3306/smartpark")

# ── Engine & Session ──────────────────────────────────────────
engine = create_async_engine(DB_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ── Base class all tables inherit from ───────────────────────
class Base(DeclarativeBase):
    pass


# ── TABLE 1: users ────────────────────────────────────────────
class UserTable(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(SAEnum("admin", "staff", "user"), nullable=False, default="user")
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Relationships
    bookings = relationship("BookingTable", back_populates="user")
    bills    = relationship("BillTable",    back_populates="user")


# ── TABLE 2: parking_slots ────────────────────────────────────
class SlotTable(Base):
    __tablename__ = "parking_slots"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    slot_number  = Column(String(10), unique=True, nullable=False, index=True)
    location     = Column(String(100), nullable=False)
    vehicle_type = Column(String(20), nullable=False, default="car")
    status       = Column(SAEnum("available", "booked", "occupied"), nullable=False, default="available")
    created_at   = Column(DateTime, default=datetime.utcnow)

    # Relationships
    bookings = relationship("BookingTable", back_populates="slot")


# ── TABLE 3: bookings ─────────────────────────────────────────
class BookingTable(Base):
    __tablename__ = "bookings"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    slot_id        = Column(Integer, ForeignKey("parking_slots.id"), nullable=False)
    status         = Column(SAEnum("pending", "active", "completed", "cancelled"), nullable=False, default="pending")
    check_in_time  = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("UserTable",    back_populates="bookings")
    slot = relationship("SlotTable",    back_populates="bookings")
    bill = relationship("BillTable",    back_populates="booking", uselist=False)


# ── TABLE 4: bills ────────────────────────────────────────────
class BillTable(Base):
    __tablename__ = "bills"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    booking_id     = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=False)
    user_id        = Column(Integer, ForeignKey("users.id"),    nullable=False)
    slot_number    = Column(String(10), nullable=False)
    check_in       = Column(DateTime, nullable=False)
    check_out      = Column(DateTime, nullable=False)
    rate_per_hour  = Column(Float, nullable=False)
    duration_hours = Column(Float, nullable=False)
    amount         = Column(Float, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)

    # Relationships
    booking = relationship("BookingTable", back_populates="bill")
    user    = relationship("UserTable",    back_populates="bills")


# ── TABLE 5: settings ─────────────────────────────────────────
class SettingTable(Base):
    __tablename__ = "settings"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    key        = Column(String(50), unique=True, nullable=False)
    value      = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── DB session dependency (used in routes) ───────────────────
async def get_db():
    """FastAPI dependency — yields a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Startup: create all tables ───────────────────────────────
async def init_db():
    """Called on app startup — creates all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ MySQL tables created (or already exist)")


async def close_db():
    await engine.dispose()
    print("🔌 MySQL connection closed")
