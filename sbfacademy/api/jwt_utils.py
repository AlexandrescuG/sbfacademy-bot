"""JWT утилиты: encode / decode access и refresh токенов."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

_SECRET = os.getenv("JWT_SECRET", "change-me-in-env")
_ALGO   = "HS256"
_ACCESS_TTL_MIN  = int(os.getenv("JWT_ACCESS_TTL_MIN",  "60"))
_REFRESH_TTL_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "30"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int) -> str:
    exp = _now() + timedelta(minutes=_ACCESS_TTL_MIN)
    payload = {"sub": str(user_id), "type": "access", "exp": exp}
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def create_refresh_token() -> tuple[str, str]:
    """Возвращает (token_id, expires_at_iso)."""
    token_id   = str(uuid.uuid4())
    expires_at = _now() + timedelta(days=_REFRESH_TTL_DAYS)
    return token_id, expires_at.strftime("%Y-%m-%d %H:%M:%S")


def decode_access_token(token: str) -> int | None:
    """Возвращает user_id или None при невалидном/просроченном токене."""
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        if payload.get("type") != "access":
            return None
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None
