"""CRM-интеграция — SBFCRM (NestJS, JWT Bearer).

Аутентификация: POST /api/auth/login → JWT → Bearer <token>.
Токен кешируется в памяти; при 401 — переаутентификация (один retry).
Notify_lead пишет в SBFCRM + шлёт Telegram-уведомление менеджеру.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import requests

from sbfacademy.core.config import (LEADS_CHANNEL_ID, MANAGER_CHAT_ID,
                                     SBFCRM_EMAIL, SBFCRM_PASSWORD, SBFCRM_URL)

log = logging.getLogger("sbfacademy.crm")

# ── JWT-пул (потокобезопасный) ─────────────────────────────────────────────────
_token: str | None = None
_token_expiry: float = 0.0          # epoch seconds
_token_lock = threading.Lock()
_TOKEN_TTL = 3600 * 20              # 20 часов (SBFCRM JWT живёт сутки)


def _login() -> str | None:
    """Логин в SBFCRM; возвращает JWT-токен или None при ошибке."""
    if not (SBFCRM_URL and SBFCRM_EMAIL and SBFCRM_PASSWORD):
        log.warning("SBFCRM not configured (SBFCRM_URL/EMAIL/PASSWORD missing)")
        return None
    try:
        resp = requests.post(
            f"{SBFCRM_URL}/api/auth/login",
            json={"email": SBFCRM_EMAIL, "password": SBFCRM_PASSWORD},
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("token")
        if not token:
            log.error("SBFCRM login: no token in response")
            return None
        log.info("SBFCRM login OK")
        return token
    except Exception as e:
        log.error("SBFCRM login failed: %s", e)
        return None


def _get_token() -> str | None:
    global _token, _token_expiry
    with _token_lock:
        if _token and time.time() < _token_expiry:
            return _token
        _token = _login()
        _token_expiry = time.time() + _TOKEN_TTL if _token else 0.0
        return _token


def _invalidate_token() -> None:
    global _token, _token_expiry
    with _token_lock:
        _token = None
        _token_expiry = 0.0


# ── lead API ───────────────────────────────────────────────────────────────────

def _post_lead(payload: dict) -> bool:
    """POST /api/leads; при 401 — одна попытка переаутентификации."""
    for attempt in range(2):
        token = _get_token()
        if not token:
            return False
        try:
            resp = requests.post(
                f"{SBFCRM_URL}/api/leads",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 401 and attempt == 0:
                log.warning("SBFCRM 401 — refresh token")
                _invalidate_token()
                continue
            if resp.status_code in (200, 201):
                log.info("SBFCRM lead created: %s", resp.json().get("id"))
                return True
            log.error("SBFCRM leads %d: %s", resp.status_code, resp.text[:200])
            return False
        except Exception as e:
            log.error("SBFCRM request error: %s", e)
            return False
    return False


def send_lead_to_sbfcrm(
    user_id: int,
    full_name: str,
    username: str,
    phone: str,
    extra_info: str = "",
    first_seen: str | None = None,
    engagement_score: int = 0,
    market_segment: str = "global",
    experience_level: str | None = None,
    deposit_range: str | None = None,
    accompaniment_interest: bool = False,
) -> bool:
    """Создаёт лид в SBFCRM. Возвращает True при успехе."""
    # ── дни в боте ──────────────────────────────────────────────────────────────
    days_in_bot = 0
    if first_seen:
        try:
            fs = datetime.strptime(first_seen[:19], "%Y-%m-%d %H:%M:%S")
            days_in_bot = max(0, (datetime.now() - fs).days)
        except Exception:
            pass

    # ── теги ────────────────────────────────────────────────────────────────────
    tags: list[str] = ["telegram-bot", f"market:{market_segment}"]
    if accompaniment_interest:
        tags.append("accompaniment-requested")
    if experience_level:
        tags.append(f"exp:{experience_level}")
    if deposit_range:
        tags.append(f"deposit:{deposit_range}")

    # ── заметки ─────────────────────────────────────────────────────────────────
    note_lines = [
        f"Telegram: @{username or '—'}",
        f"User ID: {user_id}",
        f"Дней в боте до заявки: {days_in_bot}",
        f"Рынок: {market_segment}",
        f"Вовлечённость (score): {engagement_score}",
    ]
    if experience_level:
        note_lines.append(f"Опыт: {experience_level}")
    if deposit_range:
        note_lines.append(f"Размер депозита: {deposit_range}")
    if accompaniment_interest:
        note_lines.append("⭐ Запросил сопровождение счёта")
    if extra_info:
        note_lines.append(extra_info)

    payload = {
        "name":   full_name or f"TG:{user_id}",
        "phone":  phone or None,
        "tags":   tags,
        "notes":  "\n".join(note_lines),
        "status": "NEW",
    }
    return _post_lead(payload)


# ── высокоуровневый интерфейс ─────────────────────────────────────────────────

async def notify_lead(
    bot,
    user_id: int,
    full_name: str,
    username: str,
    phone: str,
    extra_info: str = "",
    first_seen: str | None = None,
    engagement_score: int = 0,
    market_segment: str = "global",
    experience_level: str | None = None,
    deposit_range: str | None = None,
    accompaniment_interest: bool = False,
) -> None:
    """Уведомляет менеджера в Telegram и создаёт лид в SBFCRM."""
    # ── дни в боте (для Telegram-уведомления) ───────────────────────────────────
    days_in_bot = 0
    if first_seen:
        try:
            fs = datetime.strptime(first_seen[:19], "%Y-%m-%d %H:%M:%S")
            days_in_bot = max(0, (datetime.now() - fs).days)
        except Exception:
            pass

    ts  = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = (
        f"🔥 *НОВЫЙ ЛИД*\n\n"
        f"👤 Имя: {full_name}\n"
        f"🆔 Telegram: @{username or '—'}\n"
        f"📱 Телефон: {phone or '—'}\n"
        f"🔗 Профиль: tg://user?id={user_id}\n"
        f"📅 Дней в боте: {days_in_bot}\n"
        f"📊 Score: {engagement_score}\n"
    )
    if accompaniment_interest:
        msg += "⭐ Запросил сопровождение\n"
    if extra_info:
        msg += f"ℹ️ {extra_info}\n"
    msg += f"\n⏰ {ts}"

    for chat_id in [LEADS_CHANNEL_ID, MANAGER_CHAT_ID]:
        if chat_id:
            try:
                await bot.send_message(chat_id, msg, parse_mode="Markdown")
            except Exception as e:
                log.error("Lead notify error (%s): %s", chat_id, e)

    crm_ok = send_lead_to_sbfcrm(
        user_id=user_id, full_name=full_name, username=username, phone=phone,
        extra_info=extra_info, first_seen=first_seen, engagement_score=engagement_score,
        market_segment=market_segment, experience_level=experience_level,
        deposit_range=deposit_range, accompaniment_interest=accompaniment_interest,
    )
    log.info("notify_lead user=%d days_in_bot=%d crm=%s", user_id, days_in_bot, crm_ok)
