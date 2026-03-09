from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from database import get_db, UserTable
from models.models import RegisterRequest, LoginRequest
from middleware.auth import create_access_token, get_current_user

router  = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user. Email must be unique."""

    # Check duplicate email
    result = await db.execute(select(UserTable).where(UserTable.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = UserTable(
        name          = req.name,
        email         = req.email,
        password_hash = pwd_ctx.hash(req.password),
        role          = req.role.value,
    )
    db.add(user)
    await db.flush()   # get the auto-generated id before commit

    return {"message": "Registration successful.", "user_id": user.id}


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email + password. Returns JWT token."""

    result   = await db.execute(select(UserTable).where(UserTable.email == req.email))
    user_row = result.scalar_one_or_none()

    if not user_row or not pwd_ctx.verify(req.password, user_row.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token({
        "user_id": user_row.id,
        "email":   user_row.email,
        "role":    user_row.role,
    })

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":    user_row.id,
            "name":  user_row.name,
            "email": user_row.email,
            "role":  user_row.role,
        }
    }


@router.get("/me")
async def me(
    current_user: dict   = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    """Return current logged-in user's profile."""
    result   = await db.execute(select(UserTable).where(UserTable.id == current_user["user_id"]))
    user_row = result.scalar_one_or_none()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found.")

    return {
        "id":    user_row.id,
        "name":  user_row.name,
        "email": user_row.email,
        "role":  user_row.role,
    }
