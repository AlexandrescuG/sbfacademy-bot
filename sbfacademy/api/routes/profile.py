from __future__ import annotations
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sbfacademy.api.deps import current_user
from sbfacademy.core import db
from sbfacademy.core.config import DEFAULT_TIMEZONE

router = APIRouter(prefix="/api/profile", tags=["profile"])

# Basic IANA tz validation: Continent/City or UTC
_TZ_RE = re.compile(r"^[A-Z][A-Za-z_]+/[A-Z][A-Za-z_/]+$|^UTC$|^GMT$")


class ProfileBody(BaseModel):
    preferred_name:          Optional[str]  = None
    delivery_time:           Optional[str]  = None
    timezone:                Optional[str]  = None
    accompaniment_interest:  Optional[bool] = None


@router.get("")
async def get_profile(user: dict = Depends(current_user)):
    row = db.get_user(user["user_id"])
    if not row:
        raise HTTPException(404, "User not found")
    return {
        "user_id":               row["user_id"],
        "preferred_name":        row["preferred_name"] or "",
        "full_name":             row["full_name"] or "",
        "email":                 row["email"] or "",
        "delivery_time":         row["delivery_time"] or "09:00",
        "timezone":              row["timezone"] or DEFAULT_TIMEZONE,
        "accompaniment_interest": bool(row["accompaniment_interest"]),
        "auth_source":           row["auth_source"] or "telegram",
    }


@router.put("")
async def update_profile(body: ProfileBody, user: dict = Depends(current_user)):
    updates: dict = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Нет полей для обновления")
    if "timezone" in updates and not _TZ_RE.match(updates["timezone"]):
        raise HTTPException(400, f"Неверный формат timezone: {updates['timezone']}")
    if "delivery_time" in updates:
        if not re.match(r"^\d{2}:\d{2}$", updates["delivery_time"]):
            raise HTTPException(400, "delivery_time формат: HH:MM")
    db.update_user(user["user_id"], **updates)
    return {"ok": True}
