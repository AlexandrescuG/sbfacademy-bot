"""DB-слой: коннект, миграции, CRUD. DB-agnostic интерфейс (SQLite сейчас)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from sbfacademy.core.config import DB_PATH


@contextmanager
def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    # WAL — раньше был journal_mode=delete при ДВУХ уже существующих писателях
    # (бот + API-процесс); теперь market_intel/serve.py тоже читает этот файл
    # напрямую (мост аккаунтов lp.sbfconsult.com <-> SBFAcademy) — WAL заметно
    # снижает шанс "database is locked" под третьим читателем.
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── инициализация и миграции ──────────────────────────────────────────────────

def init_db() -> None:
    """Идемпотентно создаёт/дополняет схему. Безопасно вызывать при каждом старте."""
    with _conn() as con:
        c = con.cursor()
        # существующие таблицы (не трогаем, только дополняем)
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
            preferred_name TEXT, phone_number TEXT, first_seen TEXT, last_active TEXT,
            experience_level TEXT, deposit_range TEXT, already_trading TEXT,
            funnel_stage TEXT DEFAULT 'awareness', broker_interest TEXT,
            section_interest TEXT, onboarding_done INTEGER DEFAULT 0,
            followup_24h_sent INTEGER DEFAULT 0, followup_3d_sent INTEGER DEFAULT 0,
            is_subscribed INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            timestamp TEXT, action_type TEXT, details TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS statistics (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            timestamp TEXT, action_type TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")

        # новые колонки users (Phase 1)
        existing = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
        new_cols = [
            ("delivery_time",          "TEXT DEFAULT '09:00'"),
            ("market_segment",         "TEXT DEFAULT 'kz'"),
            # SPEC_tg_morning_brief_v2.md §0.4/§5: 'Asia/Almaty' was the wrong
            # default for what's now a Moldova-focused audience. Schema default
            # only -- affects new users going forward; the 63/64 existing users
            # already on 'Asia/Almaty' keep their current delivery time
            # (confirmed: that's almost certainly just the untouched default,
            # not a verified real timezone, but changing already-delivered
            # users' send time is a separate decision, not made here).
            ("timezone",               "TEXT DEFAULT 'Europe/Chisinau'"),
            ("accompaniment_interest", "INTEGER DEFAULT 0"),
            # legacy cols (если монолит ещё не добавил их):
            ("preferred_name",         "TEXT"),
            ("experience_level",       "TEXT"),
            ("deposit_range",          "TEXT"),
            ("already_trading",        "TEXT"),
            ("funnel_stage",           "TEXT DEFAULT 'awareness'"),
            ("broker_interest",        "TEXT"),
            ("section_interest",       "TEXT"),
            ("onboarding_done",        "INTEGER DEFAULT 0"),
            ("followup_24h_sent",      "INTEGER DEFAULT 0"),
            ("followup_3d_sent",       "INTEGER DEFAULT 0"),
            ("is_subscribed",          "INTEGER DEFAULT 0"),
        ]
        for col, col_type in new_cols:
            if col not in existing:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

        # новые таблицы (Phase 1)
        c.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            user_id  INTEGER,
            asset    TEXT,
            added_at TEXT,
            PRIMARY KEY (user_id, asset),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS briefings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT,
            market        TEXT,
            payload_json  TEXT,
            generated_at  TEXT,
            source_run_id TEXT,
            UNIQUE (date, market)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS delivery_log (
            user_id INTEGER,
            date    TEXT,
            sent_at TEXT,
            PRIMARY KEY (user_id, date)
        )""")

        # Phase A — email auth + devices (APK)
        new_cols_phase_a = [
            ("email",          "TEXT"),
            ("email_verified", "INTEGER DEFAULT 0"),
            ("auth_source",    "TEXT DEFAULT 'telegram'"),
            ("password_hash",  "TEXT"),
        ]
        existing = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
        for col, col_type in new_cols_phase_a:
            if col not in existing:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

        c.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
            id         TEXT PRIMARY KEY,   -- refresh token (UUID)
            user_id    INTEGER,
            created_at TEXT,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS devices (
            user_id    INTEGER,
            fcm_token  TEXT,
            platform   TEXT,               -- 'android' | 'ios'
            updated_at TEXT,
            PRIMARY KEY (user_id, fcm_token),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")

        # Phase C — привязка нескольких способов входа (telegram/google).
        # Email нарочно не здесь: у него уже есть users.email/password_hash,
        # заводить для него ещё и identity-строку — дублирование источника истины.
        c.execute("""CREATE TABLE IF NOT EXISTS auth_identities (
            provider     TEXT NOT NULL,    -- 'telegram' | 'google'
            provider_uid TEXT NOT NULL,    -- telegram user_id (как строка) | google 'sub'
            user_id      INTEGER NOT NULL,
            linked_at    TEXT,
            PRIMARY KEY (provider, provider_uid),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")

        # ── Phase B — Journal, Cheatsheets, Psychology, Calendar ─────────────
        c.execute("""CREATE TABLE IF NOT EXISTS journal_setups (
            user_id INTEGER,
            name    TEXT,
            PRIMARY KEY (user_id, name)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS journal_trades (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            instrument   TEXT,
            direction    TEXT,
            setup_tag    TEXT,
            emotion_tag  TEXT,
            entry_price  REAL,
            exit_price   REAL,
            size         REAL,
            risk_amount  REAL,
            pnl          REAL,
            r_multiple   REAL,
            opened_at    TEXT,
            closed_at    TEXT,
            notes        TEXT,
            created_at   TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS journal_theses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            instrument  TEXT,
            thesis      TEXT,
            conviction  INTEGER,
            horizon     TEXT,
            review_date TEXT,
            status      TEXT DEFAULT 'open',
            outcome     TEXT,
            created_at  TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS checklist_items (
            user_id  INTEGER,
            id       INTEGER,
            text     TEXT,
            position INTEGER,
            enabled  INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS checklist_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            trade_id     INTEGER,
            answers_json TEXT,
            completed_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS cheatsheets (
            id        TEXT PRIMARY KEY,
            category  TEXT,
            title     TEXT,
            summary   TEXT,
            body      TEXT,
            image_ref TEXT,
            tags      TEXT,
            related   TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS econ_events (
            id           TEXT PRIMARY KEY,
            ts_utc       TEXT,
            country      TEXT,
            title        TEXT,
            impact       TEXT,
            actual       TEXT,
            forecast     TEXT,
            previous     TEXT,
            source       TEXT,
            yahoo_url    TEXT,
            cheatsheet_id TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS econ_alerts (
            user_id      INTEGER,
            event_id     TEXT,
            lead_minutes INTEGER DEFAULT 60,
            PRIMARY KEY (user_id, event_id)
        )""")

        # Phase C — Email OTP (web entry)
        c.execute("""CREATE TABLE IF NOT EXISTS auth_otp (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        )""")

        # users.email uniqueness was только application-level (check-then-insert
        # в create_email_user/get_or_create_email_user) — market_intel's account
        # bridge matches shadow rows by email, so a duplicate would make that
        # match ambiguous. Partial index: NULL emails (telegram-only users) unaffected.
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_ci
            ON users(email COLLATE NOCASE) WHERE email IS NOT NULL""")


# ── users ─────────────────────────────────────────────────────────────────────

def upsert_user(user_id: int, **kwargs) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO users (user_id, first_seen, last_active) VALUES (?,?,?)",
            (user_id, now, now),
        )
        kwargs["last_active"] = now
        set_clause = ", ".join(f"{k}=?" for k in kwargs)
        con.execute(
            f"UPDATE users SET {set_clause} WHERE user_id=?",
            (*kwargs.values(), user_id),
        )


def get_user(user_id: int) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def update_user(user_id: int, **kwargs) -> None:
    """Обновляет произвольные поля пользователя."""
    if not kwargs:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kwargs["last_active"] = now
    set_clause = ", ".join(f"{k}=?" for k in kwargs)
    with _conn() as con:
        con.execute(
            f"UPDATE users SET {set_clause} WHERE user_id=?",
            (*kwargs.values(), user_id),
        )


def get_all_active_users() -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute("SELECT * FROM users").fetchall()


def log_action(user_id: int, action_type: str, details: str = "") -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            "INSERT INTO actions (user_id,timestamp,action_type,details) VALUES (?,?,?,?)",
            (user_id, now, action_type, details),
        )
        con.execute(
            "INSERT INTO statistics (user_id,timestamp,action_type) VALUES (?,?,?)",
            (user_id, now, action_type),
        )


# ── briefings ─────────────────────────────────────────────────────────────────

def upsert_briefing(date: str, market: str, payload: dict,
                    generated_at: str, source_run_id: str) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO briefings (date, market, payload_json, generated_at, source_run_id)
               VALUES (?,?,?,?,?)
               ON CONFLICT(date, market) DO UPDATE SET
                 payload_json=excluded.payload_json,
                 generated_at=excluded.generated_at,
                 source_run_id=excluded.source_run_id""",
            (date, market, json.dumps(payload, ensure_ascii=False),
             generated_at, source_run_id),
        )


def get_briefing(date: str, market: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT payload_json FROM briefings WHERE date=? AND market=?",
            (date, market),
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None


def list_briefings(market: str, limit: int = 30) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT date, market, payload_json FROM briefings WHERE market=? "
            "ORDER BY date DESC LIMIT ?",
            (market, limit),
        ).fetchall()
    result = []
    for r in rows:
        p = json.loads(r["payload_json"])
        result.append({"date": r["date"], "market": r["market"], "headline": p.get("headline", "")})
    return result


# ── delivery_log ──────────────────────────────────────────────────────────────

def already_delivered(user_id: int, date: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM delivery_log WHERE user_id=? AND date=?",
            (user_id, date),
        ).fetchone()
    return row is not None


def mark_delivered(user_id: int, date: str) -> None:
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO delivery_log (user_id,date,sent_at) VALUES (?,?,?)",
            (user_id, date, sent_at),
        )


# ── watchlist ─────────────────────────────────────────────────────────────────

def get_watchlist(user_id: int) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT asset FROM watchlist WHERE user_id=? ORDER BY added_at",
            (user_id,),
        ).fetchall()
    return [r["asset"] for r in rows]


def set_watchlist(user_id: int, assets: list[str]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute("DELETE FROM watchlist WHERE user_id=?", (user_id,))
        for asset in assets:
            con.execute(
                "INSERT OR IGNORE INTO watchlist (user_id,asset,added_at) VALUES (?,?,?)",
                (user_id, asset, now),
            )


# ── email auth (Phase A) ──────────────────────────────────────────────────────

def get_user_by_email(email: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM users WHERE email=?", (email.lower(),)
        ).fetchone()


def create_email_user(email: str, password_hash: str) -> int:
    """Создаёт пользователя по email. Возвращает user_id."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO users (email, password_hash, auth_source,
                                  email_verified, first_seen, last_active)
               VALUES (?,?,'email',1,?,?)""",
            (email.lower(), password_hash, now, now),
        )
        return cur.lastrowid


def update_user_email_auth(user_id: int, email: str, password_hash: str) -> None:
    """Привязывает email-вход к существующему пользователю (любого происхождения)."""
    with _conn() as con:
        con.execute(
            """UPDATE users SET email=?, password_hash=?,
               auth_source=CASE WHEN auth_source='email' THEN 'email' ELSE 'both' END,
               email_verified=1 WHERE user_id=?""",
            (email.lower(), password_hash, user_id),
        )


# ── auth_identities (telegram/google — привязка нескольких способов входа) ────

def get_identity(provider: str, provider_uid: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM auth_identities WHERE provider=? AND provider_uid=?",
            (provider, str(provider_uid)),
        ).fetchone()


def link_identity(provider: str, provider_uid: str, user_id: int) -> None:
    """Привязывает identity к user_id. Вызывающая сторона должна была уже
    проверить через get_identity(), что provider_uid свободен или уже принадлежит
    этому же user_id — иначе тут случайно перепривяжется чужой аккаунт."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            """INSERT INTO auth_identities (provider, provider_uid, user_id, linked_at)
               VALUES (?,?,?,?)
               ON CONFLICT(provider, provider_uid) DO UPDATE SET user_id=excluded.user_id""",
            (provider, str(provider_uid), user_id, now),
        )


def unlink_identity(provider: str, user_id: int) -> None:
    with _conn() as con:
        con.execute(
            "DELETE FROM auth_identities WHERE provider=? AND user_id=?",
            (provider, user_id),
        )


def list_identities(user_id: int) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT provider FROM auth_identities WHERE user_id=?", (user_id,)
        ).fetchall()
        return [r["provider"] for r in rows]


def resolve_telegram_user(tg_id: int, username: str | None = None, full_name: str | None = None) -> int:
    """Канонический user_id для этого Telegram-аккаунта.

    Обычно это сам tg_id (историческая схема: user_id бота = telegram id).
    Но если этот tg_id был явно привязан (/api/auth/link/telegram) к другому
    профилю — например, к аккаунту, заведённому через email/Google — то
    входить нужно в ТОТ профиль, а не создавать/трогать отдельную строку tg_id.
    """
    identity = get_identity("telegram", str(tg_id))
    target_id = identity["user_id"] if identity else tg_id
    if target_id == tg_id:
        upsert_user(target_id, username=username, full_name=full_name)
    else:
        upsert_user(target_id)
    link_identity("telegram", str(tg_id), target_id)
    return target_id


def create_provider_user(auth_source: str, full_name: str | None = None) -> int:
    """Новый пользователь без email/telegram-id (например, Google без e-mail)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO users (auth_source, full_name, first_seen, last_active) VALUES (?,?,?,?)",
            (auth_source, full_name, now, now),
        )
        return cur.lastrowid


def clear_user_email(user_id: int) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE users SET email=NULL, password_hash=NULL, email_verified=0 WHERE user_id=?",
            (user_id,),
        )


# ── auth_sessions (refresh tokens) ────────────────────────────────────────────

def create_session(session_id: str, user_id: int, expires_at: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            "INSERT INTO auth_sessions (id,user_id,created_at,expires_at) VALUES (?,?,?,?)",
            (session_id, user_id, now, expires_at),
        )


def get_session(session_id: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM auth_sessions WHERE id=?", (session_id,)
        ).fetchone()


def delete_session(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM auth_sessions WHERE id=?", (session_id,))


def purge_expired_sessions() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))


# ── auth_otp ──────────────────────────────────────────────────────────────────

def create_otp(email: str, code: str, expires_at: str) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO auth_otp (email,code,created_at,expires_at) VALUES (?,?,?,?)",
            (email.lower(), code, now, expires_at),
        )
        return cur.lastrowid


def get_latest_otp(email: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM auth_otp WHERE email=? ORDER BY id DESC LIMIT 1",
            (email.lower(),),
        ).fetchone()


def mark_otp_used(otp_id: int) -> None:
    with _conn() as con:
        con.execute("UPDATE auth_otp SET used=1 WHERE id=?", (otp_id,))


def get_or_create_email_user(email: str) -> int:
    """Возвращает user_id существующего пользователя или создаёт нового без пароля."""
    row = get_user_by_email(email)
    if row:
        upsert_user(row["user_id"])
        return row["user_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO users (email, auth_source, email_verified, first_seen, last_active)
               VALUES (?,?,1,?,?)""",
            (email.lower(), "email_otp", now, now),
        )
        return cur.lastrowid


# ── devices (FCM) ─────────────────────────────────────────────────────────────

def upsert_device(user_id: int, fcm_token: str, platform: str = "android") -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            """INSERT INTO devices (user_id,fcm_token,platform,updated_at) VALUES (?,?,?,?)
               ON CONFLICT(user_id,fcm_token) DO UPDATE SET
                 platform=excluded.platform, updated_at=excluded.updated_at""",
            (user_id, fcm_token, platform, now),
        )


def get_fcm_tokens(user_id: int) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT fcm_token FROM devices WHERE user_id=?", (user_id,)
        ).fetchall()
    return [r["fcm_token"] for r in rows]


def get_all_devices() -> list[sqlite3.Row]:
    """Все активные устройства (для рассылки брифинга)."""
    with _conn() as con:
        return con.execute("SELECT * FROM devices").fetchall()


# ── journal_trades ─────────────────────────────────────────────────────────────

_DEFAULT_SETUPS = ["breakout", "pullback", "range", "reversal", "news"]
_VALID_EMOTIONS = {"calm", "fomo", "fear", "revenge", "tired", "confident", "bored"}

def ensure_default_setups(user_id: int) -> None:
    with _conn() as con:
        for s in _DEFAULT_SETUPS:
            con.execute("INSERT OR IGNORE INTO journal_setups (user_id,name) VALUES (?,?)",
                        (user_id, s))

def get_setups(user_id: int) -> list[str]:
    with _conn() as con:
        rows = con.execute("SELECT name FROM journal_setups WHERE user_id=? ORDER BY name",
                           (user_id,)).fetchall()
    return [r["name"] for r in rows]

def add_setup(user_id: int, name: str) -> None:
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO journal_setups (user_id,name) VALUES (?,?)",
                    (user_id, name))

def delete_setup(user_id: int, name: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM journal_setups WHERE user_id=? AND name=?", (user_id, name))

def create_trade(user_id: int, **fields) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pnl = fields.get("pnl")
    risk = fields.get("risk_amount")
    if pnl is not None and risk:
        fields["r_multiple"] = round(pnl / risk, 2)
    fields["created_at"] = now
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    with _conn() as con:
        cur = con.execute(
            f"INSERT INTO journal_trades (user_id,{cols}) VALUES (?," + placeholders + ")",
            (user_id, *fields.values()),
        )
        return cur.lastrowid

def update_trade(trade_id: int, user_id: int, **fields) -> bool:
    if not fields:
        return False
    pnl = fields.get("pnl")
    risk = fields.get("risk_amount")
    if pnl is not None and risk:
        fields["r_multiple"] = round(pnl / risk, 2)
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as con:
        cur = con.execute(
            f"UPDATE journal_trades SET {set_clause} WHERE id=? AND user_id=?",
            (*fields.values(), trade_id, user_id),
        )
        return cur.rowcount > 0

def delete_trade(trade_id: int, user_id: int) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM journal_trades WHERE id=? AND user_id=?",
                          (trade_id, user_id))
        return cur.rowcount > 0

def get_trade(trade_id: int, user_id: int) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM journal_trades WHERE id=? AND user_id=?",
                           (trade_id, user_id)).fetchone()

def list_trades(user_id: int, limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM journal_trades WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()

def list_all_trades(user_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM journal_trades WHERE user_id=? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()


# ── journal_theses ─────────────────────────────────────────────────────────────

def create_thesis(user_id: int, **fields) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields["created_at"] = now
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    with _conn() as con:
        cur = con.execute(
            f"INSERT INTO journal_theses (user_id,{cols}) VALUES (?," + placeholders + ")",
            (user_id, *fields.values()),
        )
        return cur.lastrowid

def list_theses(user_id: int, status: str | None = None) -> list[sqlite3.Row]:
    with _conn() as con:
        if status:
            return con.execute(
                "SELECT * FROM journal_theses WHERE user_id=? AND status=? ORDER BY created_at DESC",
                (user_id, status),
            ).fetchall()
        return con.execute(
            "SELECT * FROM journal_theses WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()

def update_thesis(thesis_id: int, user_id: int, **fields) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as con:
        cur = con.execute(
            f"UPDATE journal_theses SET {set_clause} WHERE id=? AND user_id=?",
            (*fields.values(), thesis_id, user_id),
        )
        return cur.rowcount > 0

def get_theses_due_today() -> list[sqlite3.Row]:
    today = datetime.now().strftime("%Y-%m-%d")
    with _conn() as con:
        return con.execute(
            "SELECT * FROM journal_theses WHERE review_date<=? AND status='open'",
            (today,),
        ).fetchall()


# ── checklist ─────────────────────────────────────────────────────────────────

_DEFAULT_CHECKLIST = [
    "Выспался и в ресурсном состоянии?",
    "Есть чёткий план на сделку?",
    "Риск посчитан заранее?",
    "Не отыгрываю предыдущий убыток?",
]

def ensure_default_checklist(user_id: int) -> None:
    with _conn() as con:
        count = con.execute("SELECT COUNT(*) FROM checklist_items WHERE user_id=?",
                            (user_id,)).fetchone()[0]
        if count == 0:
            for i, text in enumerate(_DEFAULT_CHECKLIST):
                con.execute(
                    "INSERT OR IGNORE INTO checklist_items (user_id,id,text,position,enabled) VALUES (?,?,?,?,1)",
                    (user_id, i + 1, text, i),
                )

def get_checklist(user_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM checklist_items WHERE user_id=? AND enabled=1 ORDER BY position",
            (user_id,),
        ).fetchall()

def save_checklist_run(user_id: int, answers: dict, trade_id: int | None = None) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO checklist_runs (user_id,trade_id,answers_json,completed_at) VALUES (?,?,?,?)",
            (user_id, trade_id, json.dumps(answers), now),
        )
        return cur.lastrowid

def update_checklist_item(user_id: int, item_id: int, **fields) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _conn() as con:
        cur = con.execute(
            f"UPDATE checklist_items SET {set_clause} WHERE user_id=? AND id=?",
            (*fields.values(), user_id, item_id),
        )
        return cur.rowcount > 0


# ── cheatsheets ───────────────────────────────────────────────────────────────

def seed_cheatsheets(cards: list[dict]) -> None:
    with _conn() as con:
        for c_item in cards:
            con.execute(
                """INSERT OR IGNORE INTO cheatsheets (id,category,title,summary,body,image_ref,tags,related)
                   VALUES (:id,:category,:title,:summary,:body,:image_ref,:tags,:related)""",
                c_item,
            )

def get_cheatsheet(sheet_id: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM cheatsheets WHERE id=?", (sheet_id,)).fetchone()

def search_cheatsheets(q: str = "", category: str = "") -> list[sqlite3.Row]:
    with _conn() as con:
        if q and category:
            return con.execute(
                "SELECT * FROM cheatsheets WHERE category=? AND (title LIKE ? OR tags LIKE ?) ORDER BY title",
                (category, f"%{q}%", f"%{q}%"),
            ).fetchall()
        if q:
            return con.execute(
                "SELECT * FROM cheatsheets WHERE title LIKE ? OR tags LIKE ? ORDER BY title",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        if category:
            return con.execute(
                "SELECT * FROM cheatsheets WHERE category=? ORDER BY title",
                (category,),
            ).fetchall()
        return con.execute("SELECT * FROM cheatsheets ORDER BY category, title").fetchall()


# ── econ_events ───────────────────────────────────────────────────────────────

def upsert_econ_event(event: dict) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO econ_events (id,ts_utc,country,title,impact,actual,forecast,previous,source,yahoo_url,cheatsheet_id)
               VALUES (:id,:ts_utc,:country,:title,:impact,:actual,:forecast,:previous,:source,:yahoo_url,:cheatsheet_id)
               ON CONFLICT(id) DO UPDATE SET
                 actual=excluded.actual, forecast=excluded.forecast,
                 previous=excluded.previous, ts_utc=excluded.ts_utc""",
            event,
        )

def list_econ_events(date: str | None = None, impact: str | None = None,
                     country: str | None = None) -> list[sqlite3.Row]:
    clauses, params = [], []
    if date:
        clauses.append("ts_utc LIKE ?")
        params.append(f"{date}%")
    if impact:
        clauses.append("impact=?")
        params.append(impact)
    if country:
        clauses.append("country=?")
        params.append(country)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as con:
        return con.execute(
            f"SELECT * FROM econ_events {where} ORDER BY ts_utc",
            params,
        ).fetchall()

def get_econ_event(event_id: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM econ_events WHERE id=?", (event_id,)).fetchone()

def set_econ_alert(user_id: int, event_id: str, lead_minutes: int = 60) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO econ_alerts (user_id,event_id,lead_minutes) VALUES (?,?,?)
               ON CONFLICT(user_id,event_id) DO UPDATE SET lead_minutes=excluded.lead_minutes""",
            (user_id, event_id, lead_minutes),
        )

def delete_econ_alert(user_id: int, event_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM econ_alerts WHERE user_id=? AND event_id=?",
                    (user_id, event_id))

def get_user_econ_alerts(user_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            """SELECT a.*, e.ts_utc, e.title, e.impact, e.country
               FROM econ_alerts a JOIN econ_events e ON a.event_id=e.id
               WHERE a.user_id=? ORDER BY e.ts_utc""",
            (user_id,),
        ).fetchall()

def get_due_econ_alerts(window_minutes: int = 5) -> list[sqlite3.Row]:
    """Возвращает алерты, которые нужно отправить в ближайшие window_minutes минут."""
    from datetime import timedelta, timezone as _tz
    now = datetime.now(_tz.utc)
    with _conn() as con:
        rows = con.execute(
            """SELECT a.user_id, a.lead_minutes, e.id as event_id,
                      e.ts_utc, e.title, e.country, e.impact
               FROM econ_alerts a JOIN econ_events e ON a.event_id=e.id""",
        ).fetchall()
    due = []
    for r in rows:
        try:
            ev_ts = datetime.fromisoformat(r["ts_utc"].replace("Z", "+00:00"))
            fire_at = ev_ts - timedelta(minutes=r["lead_minutes"])
            if fire_at <= now <= ev_ts:
                due.append(r)
        except Exception:
            pass
    return due
