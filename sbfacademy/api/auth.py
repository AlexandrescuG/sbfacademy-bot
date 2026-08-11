"""Валидация входящих credentials.

validate_init_data  — Telegram Mini App (HMAC-SHA256, "WebAppData")
decode_bearer       — JWT Bearer (standalone APK)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from sbfacademy.api.jwt_utils import decode_access_token

_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
_MAX_AGE   = int(os.getenv("TMA_MAX_AGE_SEC", "86400"))


def validate_init_data(init_data: str) -> dict | None:
    """Telegram initData → распарсенные поля или None."""
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", _BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc   = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        return None
    auth_date = int(parsed.get("auth_date", "0"))
    if _MAX_AGE and (time.time() - auth_date) > _MAX_AGE:
        return None
    if "user" in parsed:
        parsed["user"] = json.loads(parsed["user"])
    return parsed


def decode_bearer(token: str) -> int | None:
    """JWT Bearer → user_id или None."""
    return decode_access_token(token)
