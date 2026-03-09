from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY         = os.getenv("SECRET_KEY", "fallback-secret")
ALGORITHM          = "HS256"
TOKEN_EXPIRE_HOURS = 24

bearer_scheme = HTTPBearer()


def create_access_token(data: dict) -> str:
    """Create a signed JWT valid for 24 hours."""
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode JWT. Raises 401 on invalid/expired token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again."
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """Dependency — returns current user info from JWT token."""
    payload = decode_token(credentials.credentials)
    return {
        "user_id": payload.get("user_id"),
        "email":   payload.get("email"),
        "role":    payload.get("role"),
    }


def require_roles(*allowed_roles: str):
    """
    Role guard factory.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles("admin"))])
        @router.post("/checkin", dependencies=[Depends(require_roles("admin","staff"))])
    """
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required: {list(allowed_roles)}. "
                       f"Your role: '{current_user['role']}'"
            )
        return current_user
    return checker


# Shortcut dependencies
require_admin = Depends(require_roles("admin"))
require_staff = Depends(require_roles("admin", "staff"))
require_user  = Depends(get_current_user)
