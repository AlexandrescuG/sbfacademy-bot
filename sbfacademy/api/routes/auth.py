"""Аутентификация: email/password, email-OTP, Telegram Login Widget, Google.

POST /api/auth/register      body {email, password}       → {access_token, refresh_token}
POST /api/auth/login         body {email, password}       → {access_token, refresh_token}
POST /api/auth/refresh       body {refresh_token}         → {access_token}
POST /api/auth/request-code  body {email}                 → 200
POST /api/auth/verify        body {email, code}           → {access_token, refresh_token}
POST /api/auth/telegram      body <telegram-widget-data>  → {access_token, refresh_token}
POST /api/auth/google        body {credential}            → {access_token, refresh_token}
POST /api/auth/link/email    body {email, password}       → {ok} (нужен Bearer)
POST /api/auth/link/telegram body <telegram-widget-data>  → {ok} (нужен Bearer)
POST /api/auth/link/google   body {credential}            → {ok} (нужен Bearer)
DELETE /api/auth/link/{provider}                          → {ok} (нужен Bearer)
GET  /api/me                                               → профиль + linked_providers
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import random
import re
import secrets
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import bcrypt
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from sbfacademy.api.deps import current_user
from sbfacademy.api.jwt_utils import (create_access_token, create_refresh_token)
from sbfacademy.core import db
from sbfacademy.core.config import DEFAULT_TIMEZONE
from sbfacademy.core.crm import notify_lead

log = logging.getLogger("sbfacademy.api.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── schemas ───────────────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль должен быть не менее 8 символов")
        return v


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class OtpRequestBody(BaseModel):
    email: EmailStr


class OtpVerifyBody(BaseModel):
    email: EmailStr
    code: str


class TelegramWidgetBody(BaseModel):
    """Данные, которые Telegram Login Widget возвращает в data-onauth callback."""
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class GoogleAuthBody(BaseModel):
    credential: str  # Google ID token (JWT) из Google Identity Services


class LinkEmailBody(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль должен быть не менее 8 символов")
        return v


# ── helpers ───────────────────────────────────────────────────────────────────

def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_pw(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _issue_tokens(user_id: int) -> dict:
    access  = create_access_token(user_id)
    ref_id, expires_at = create_refresh_token()
    db.create_session(ref_id, user_id, expires_at)
    return {"access_token": access, "refresh_token": ref_id, "token_type": "bearer"}


_TG_WIDGET_MAX_AGE = 86400  # сек — данные виджета старше суток не принимаем


def _validate_telegram_widget(data: dict) -> bool:
    """HMAC-проверка данных Telegram Login Widget.

    Отличается от validate_init_data (Mini App): там secret = HMAC("WebAppData", token),
    здесь secret = SHA256(token) напрямую — два разных алгоритма Telegram, не путать.
    См. https://core.telegram.org/widgets/login#checking-authorization
    """
    data = dict(data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return False
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()) if v is not None)
    bot_token = os.getenv("BOT_TOKEN", "")
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, received_hash):
        return False
    auth_date = int(data.get("auth_date", 0))
    if (time.time() - auth_date) > _TG_WIDGET_MAX_AGE:
        return False
    return True


def _verify_google_token(credential: str) -> dict:
    """Проверяет Google ID token через tokeninfo endpoint (без доп. зависимостей)."""
    try:
        r = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential}, timeout=8,
        )
    except Exception as e:
        log.error("Google tokeninfo request failed: %s", e)
        raise HTTPException(401, "Не удалось проверить Google-токен")
    if r.status_code != 200:
        raise HTTPException(401, "Неверный или истёкший Google-токен")
    claims = r.json()
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if client_id and claims.get("aud") != client_id:
        raise HTTPException(401, "Google-токен выдан не для этого приложения")
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Неверный издатель Google-токена")
    return claims


# Google Identity Services (renderButton/One Tap) отказывается работать внутри
# встроенных WebView — в т.ч. Telegram Mini Apps — и глушится там пустым экраном
# (антифишинговая политика Google, а не наш баг). Обход: открыть OAuth-экран в
# СИСТЕМНОМ браузере телефона через Telegram.WebApp.openLink(), а не рисовать
# кнопку внутри Mini App. Раз callback тогда физически не может дёрнуть наш JS
# (это уже другая вкладка/контекст), связываем запрос и его результат вручную
# через одноразовый state, всплывающий в статической google-callback.html.
_pending_google_links: dict[str, tuple[int, str, float]] = {}  # state -> (user_id, nonce, expires_at)
_PENDING_LINK_TTL_SEC = 600


def _cleanup_pending_links() -> None:
    now = time.time()
    for k in [k for k, v in _pending_google_links.items() if v[2] < now]:
        _pending_google_links.pop(k, None)


def _link_google_identity(user_id: int, claims: dict) -> dict:
    sub = claims["sub"]
    identity = db.get_identity("google", sub)
    if identity and identity["user_id"] != user_id:
        raise HTTPException(409, "Этот Google-аккаунт уже привязан к другому профилю")
    db.link_identity("google", sub, user_id)
    db.log_action(user_id, "link_google", claims.get("email", ""))
    return {"ok": True, "linked": "google"}


def _resolve_google_user(claims: dict) -> int:
    sub = claims["sub"]
    identity = db.get_identity("google", sub)
    if identity:
        user_id = identity["user_id"]
        db.upsert_user(user_id)
        return user_id
    email = claims.get("email")
    email_verified = str(claims.get("email_verified", "")).lower() in ("true", "1")
    if email and email_verified:
        user_id = db.get_or_create_email_user(email)
    else:
        user_id = db.create_provider_user("google", full_name=claims.get("name"))
    db.link_identity("google", sub, user_id)
    return user_id


def _send_otp_email(to_email: str, code: str) -> None:
    """Отправляет OTP. При отсутствии SMTP-конфига пишет в лог (dev mode)."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        log.warning("DEV MODE — OTP для %s: %s", to_email, code)
        return
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    body = f"Ваш код входа в SBF Academy: {code}\n\nКод действителен 10 минут."
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"SBF Academy — код входа: {code}"
    msg["From"] = smtp_from
    msg["To"] = to_email
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_from, [to_email], msg.as_string())


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/request-code")
async def request_code(body: OtpRequestBody):
    email = body.email.lower()
    # rate-limit: не чаще одного кода в 60 секунд
    last = db.get_latest_otp(email)
    if last:
        created = datetime.strptime(last["created_at"], "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - created).total_seconds() < 60:
            raise HTTPException(429, "Подождите 60 секунд перед повторным запросом")
    code = str(random.randint(100000, 999999))
    expires_at = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    db.create_otp(email, code, expires_at)
    try:
        _send_otp_email(email, code)
    except Exception as e:
        log.error("OTP email send failed for %s: %s", email, e)
        raise HTTPException(500, "Не удалось отправить код. Попробуйте позже.")
    return {"ok": True, "detail": "Код отправлен на почту"}


@router.post("/verify")
async def verify_otp(body: OtpVerifyBody):
    email = body.email.lower()
    otp_row = db.get_latest_otp(email)
    if not otp_row:
        raise HTTPException(400, "Код не найден. Запросите новый.")
    if otp_row["used"]:
        raise HTTPException(400, "Код уже использован. Запросите новый.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if otp_row["expires_at"] < now:
        raise HTTPException(400, "Код истёк. Запросите новый.")
    if otp_row["code"] != body.code.strip():
        raise HTTPException(400, "Неверный код")
    db.mark_otp_used(otp_row["id"])
    user_id = db.get_or_create_email_user(email)
    db.log_action(user_id, "otp_login", email)
    log.info("otp login user_id=%d email=%s", user_id, email)
    return _issue_tokens(user_id)


@router.post("/telegram")
async def login_telegram(body: TelegramWidgetBody):
    """Telegram Login Widget (сайт/Mini App вне Telegram). НЕ путать с /api/auth/tma."""
    if not _validate_telegram_widget(body.model_dump(exclude_none=True)):
        raise HTTPException(401, "Неверные данные Telegram Login Widget")
    full_name = f"{body.first_name or ''} {body.last_name or ''}".strip()
    user_id = db.resolve_telegram_user(body.id, username=body.username, full_name=full_name or None)
    db.log_action(user_id, "telegram_login", body.username or "")
    return _issue_tokens(user_id)


@router.post("/google")
async def login_google(body: GoogleAuthBody):
    claims = _verify_google_token(body.credential)
    user_id = _resolve_google_user(claims)
    db.log_action(user_id, "google_login", claims.get("email", ""))
    return _issue_tokens(user_id)


@router.post("/link/email")
async def link_email(body: LinkEmailBody, user: dict = Depends(current_user)):
    email = body.email.lower()
    existing = db.get_user_by_email(email)
    if existing and existing["user_id"] != user["user_id"]:
        raise HTTPException(409, "Этот email уже привязан к другому профилю")
    db.update_user_email_auth(user["user_id"], email, _hash_pw(body.password))
    db.log_action(user["user_id"], "link_email", email)
    return {"ok": True, "linked": "email"}


@router.post("/link/telegram")
async def link_telegram(body: TelegramWidgetBody, user: dict = Depends(current_user)):
    if not _validate_telegram_widget(body.model_dump(exclude_none=True)):
        raise HTTPException(401, "Неверные данные Telegram Login Widget")
    tg_id = body.id
    identity = db.get_identity("telegram", str(tg_id))
    if identity and identity["user_id"] != user["user_id"]:
        raise HTTPException(409, "Этот Telegram-аккаунт уже привязан к другому профилю")
    if not identity and tg_id != user["user_id"] and db.get_user(tg_id) is not None:
        # У tg_id уже есть отдельная история (например, использовал бота раньше) —
        # молча объединять с текущим профилем нельзя, это может смешать чужие данные.
        raise HTTPException(409, "Этот Telegram уже использовался отдельно — обратитесь в поддержку для объединения аккаунтов")
    db.link_identity("telegram", str(tg_id), user["user_id"])
    db.log_action(user["user_id"], "link_telegram", body.username or "")
    return {"ok": True, "linked": "telegram"}


@router.post("/link/google")
async def link_google(body: GoogleAuthBody, user: dict = Depends(current_user)):
    claims = _verify_google_token(body.credential)
    return _link_google_identity(user["user_id"], claims)


@router.post("/google/link-start")
async def google_link_start(user: dict = Depends(current_user)):
    """Шаг 1 редирект-обхода: готовим одноразовый state+nonce и ссылку на Google,
    которую откроет Telegram.WebApp.openLink() в системном браузере."""
    _cleanup_pending_links()
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(500, "GOOGLE_CLIENT_ID не настроен")
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(16)
    _pending_google_links[state] = (user["user_id"], nonce, time.time() + _PENDING_LINK_TTL_SEC)
    redirect_uri = os.getenv("PUBLIC_BASE_URL", "https://web.sbfconsult.com") + "/google-callback.html"
    from urllib.parse import urlencode
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "id_token", "scope": "openid email profile",
        "nonce": nonce, "state": state, "prompt": "select_account",
    }
    return {"oauth_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


class GoogleLinkFinishBody(BaseModel):
    state: str
    id_token: str


@router.post("/google/link-finish")
async def google_link_finish(body: GoogleLinkFinishBody):
    """Шаг 2: дёргается САМОЙ callback-страницей (уже вне Telegram, в системном
    браузере) — поэтому без Bearer/tma, личность запроса подтверждается state'ом."""
    _cleanup_pending_links()
    pending = _pending_google_links.get(body.state)
    if not pending:
        raise HTTPException(400, "Ссылка устарела или уже использована. Попробуйте привязать ещё раз.")
    user_id, nonce, _ = pending
    claims = _verify_google_token(body.id_token)
    if claims.get("nonce") != nonce:
        raise HTTPException(401, "Несовпадение nonce")
    _pending_google_links.pop(body.state, None)
    return _link_google_identity(user_id, claims)


@router.delete("/link/{provider}")
async def unlink(provider: str, user: dict = Depends(current_user)):
    if provider not in ("email", "telegram", "google"):
        raise HTTPException(400, "Неизвестный способ входа")
    row = db.get_user(user["user_id"])
    linked = set(db.list_identities(user["user_id"]))
    if row and row["email"]:
        linked.add("email")
    if provider not in linked:
        raise HTTPException(400, "Этот способ входа не привязан")
    if len(linked) <= 1:
        raise HTTPException(400, "Нельзя отвязать последний способ входа")
    if provider == "email":
        db.clear_user_email(user["user_id"])
    else:
        db.unlink_identity(provider, user["user_id"])
    db.log_action(user["user_id"], "unlink_" + provider)
    return {"ok": True, "unlinked": provider}


@router.post("/register")
async def register(body: RegisterBody):
    email = body.email.lower()
    if db.get_user_by_email(email):
        raise HTTPException(409, "Email уже зарегистрирован")
    pw_hash = _hash_pw(body.password)
    user_id = db.create_email_user(email, pw_hash)
    db.log_action(user_id, "register", email)
    log.info("new email user %d %s", user_id, email)
    # Пишем лид в SBFCRM (без телефона, без Telegram)
    try:
        from sbfacademy.core.crm import send_lead_to_sbfcrm
        send_lead_to_sbfcrm(
            user_id=user_id, full_name=email, username="", phone="",
            extra_info="Регистрация через APK", market_segment="global",
        )
    except Exception as e:
        log.warning("CRM lead on register failed: %s", e)
    return _issue_tokens(user_id)


@router.post("/login")
async def login(body: LoginBody):
    email = body.email.lower()
    row = db.get_user_by_email(email)
    if not row or not row["password_hash"]:
        raise HTTPException(401, "Неверный email или пароль")
    if not _check_pw(body.password, row["password_hash"]):
        raise HTTPException(401, "Неверный email или пароль")
    user_id = row["user_id"]
    db.upsert_user(user_id)  # обновляет last_active
    db.log_action(user_id, "login", email)
    return _issue_tokens(user_id)


@router.post("/refresh")
async def refresh(body: RefreshBody):
    session = db.get_session(body.refresh_token)
    if not session:
        raise HTTPException(401, "Refresh token не найден или истёк")
    from datetime import datetime
    if session["expires_at"] < datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
        db.delete_session(body.refresh_token)
        raise HTTPException(401, "Refresh token истёк")
    user_id = session["user_id"]
    # Rotate: старый удаляем, выдаём новую пару
    db.delete_session(body.refresh_token)
    return _issue_tokens(user_id)


@router.get("/logout")
async def logout(authorization: str = "", user: dict = Depends(current_user)):
    # Если это Bearer — инвалидируем сессию (refresh токен клиент должен прислать отдельно)
    db.log_action(user["user_id"], "logout")
    return {"ok": True}


# ── /api/me (не в /auth/ prefix, но логически сюда) ──────────────────────────
me_router = APIRouter(tags=["auth"])


@me_router.get("/api/me")
async def me(user: dict = Depends(current_user)):
    row = db.get_user(user["user_id"])
    if not row:
        raise HTTPException(404, "User not found")
    linked = db.list_identities(row["user_id"])
    if row["email"]:
        linked = ["email"] + linked
    return {
        "user_id":               row["user_id"],
        "email":                 row["email"] or "",
        "preferred_name":        row["preferred_name"] or row["full_name"] or "",
        "delivery_time":         row["delivery_time"] or "09:00",
        "timezone":              row["timezone"] or DEFAULT_TIMEZONE,
        "accompaniment_interest": bool(row["accompaniment_interest"]),
        "auth_source":           row["auth_source"] or "telegram",
        "linked_providers":      linked,
    }
