"""
seed_users.py
=============
Run ONCE after first startup to create 3 demo users.

Usage:
    python seed_users.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from passlib.context import CryptContext
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

DB_URL  = os.getenv("DB_URL", "mysql+aiomysql://root:password@localhost:3306/smartpark")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_USERS = [
    {"name": "Admin User",   "email": "admin@campus.com", "password": "admin123", "role": "admin"},
    {"name": "Staff Member", "email": "staff@campus.com", "password": "staff123", "role": "staff"},
    {"name": "Test Student", "email": "user@campus.com",  "password": "user123",  "role": "user"},
]

async def seed():
    # Import here so tables are already created by init_db()
    from database import UserTable, Base

    engine  = create_async_engine(DB_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        created = 0
        for u in DEMO_USERS:
            result = await db.execute(select(UserTable).where(UserTable.email == u["email"]))
            if result.scalar_one_or_none():
                print(f"⚠️  Already exists: {u['email']}")
                continue

            user = UserTable(
                name          = u["name"],
                email         = u["email"],
                password_hash = pwd_ctx.hash(u["password"]),
                role          = u["role"],
            )
            db.add(user)
            created += 1
            print(f"✅ Created {u['role']}: {u['email']} / {u['password']}")

        await db.commit()

    await engine.dispose()
    print(f"\n🎉 Done. {created} user(s) created.")
    print("\nDemo credentials:")
    print("  Admin → admin@campus.com / admin123")
    print("  Staff → staff@campus.com / staff123")
    print("  User  → user@campus.com  / user123")

if __name__ == "__main__":
    asyncio.run(seed())
