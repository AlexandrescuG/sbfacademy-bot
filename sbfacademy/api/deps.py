"""FastAPI-зависимость current_user — принимает tma initData ИЛИ JWT Bearer.

Authorization: tma <initData>   → Telegram Mini App
Authorization: Bearer <token>   → standalone APK (email auth)
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from sbfacademy.api.auth import decode_bearer, validate_init_data
from sbfacademy.core import db


async def current_user(authorization: str = Header(default="")) -> dict:
    """
    Возвращает dict с ключами: user_id, source ('telegram'|'email'), email?, telegram_id?
    """
    if not authorization:
        raise HTTPException(401, "Authorization header missing")

    # ── Telegram Mini App ──────────────────────────────────────────────────────
    if authorization.startswith("tma "):
        data = validate_init_data(authorization[4:])
        if not data or "user" not in data:
            raise HTTPException(401, "Invalid initData")
        tg_user = data["user"]
        tg_id   = tg_user["id"]
        # resolve_telegram_user учитывает привязку (/api/auth/link/telegram) —
        # если этот Telegram явно привязан к другому профилю (email/Google),
        # заходим в тот профиль, а не создаём/используем отдельную запись tg_id.
        user_id = db.resolve_telegram_user(
            tg_id,
            username=tg_user.get("username"),
            full_name=f"{tg_user.get('first_name','')} {tg_user.get('last_name','')}".strip(),
        )
        row = db.get_user(user_id)
        return {"user_id": user_id, "source": "telegram", "telegram_id": tg_id,
                "email": row["email"] if row else None}

    # ── JWT Bearer (APK) ───────────────────────────────────────────────────────
    if authorization.startswith("Bearer "):
        user_id = decode_bearer(authorization[7:])
        if not user_id:
            raise HTTPException(401, "Invalid or expired token")
        row = db.get_user(user_id)
        if not row:
            raise HTTPException(401, "User not found")
        return {"user_id": user_id, "source": "email",
                "email": row["email"], "telegram_id": row["user_id"]}

    raise HTTPException(401, "Unsupported auth scheme")
