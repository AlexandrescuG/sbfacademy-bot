"""Генерация брифинга: читает @SBFEconomics за 24ч → Claude → briefings.

НЕ ИСПОЛЬЗУЕТСЯ (SPEC_tg_morning_brief_v2.md §0.5, 29.07.2026): push.py::ingest_job
раньше пробовал этот путь первым, с фоллбэком на market_intel. TG_API_HASH и
ANTHROPIC_API_KEY в .env пустые -- run() падал на первой строке при каждом
вызове, ни одного успешного прогона не было. Не чинили: тот же Telethon-сессионный
файл (sbf_session.session) одновременно использует боевой процесс Vorovka2 --
второй клиент на той же сессии — реальный риск конфликта, не гипотетический.
Плюс структурированная часть пуша (§2) теперь и так берёт данные из уже
посчитанного market_intel-пайплайна, а не из отдельного LLM-синтеза здесь --
архитектурно этот файл больше не нужен, не только из-за credentials. Оставлен
в репозитории на случай, если решение по credentials/архитектуре изменится.

Запуск:
    python -m sbfacademy.briefing.generate
    python -m sbfacademy.briefing.generate 2026-06-27
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env из директории бота
_BOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(str(_BOT_DIR / ".env"))

from sbfacademy.core import db
from sbfacademy.core.models import Briefing, Theme

log = logging.getLogger("sbfacademy.briefing.generate")

# Telethon — берём сессию и credentials от vorovka2
_VOROVKA_DIR = Path(os.getenv("VOROVKA_DIR", "/mnt/sbfdata/Vorovka2"))
_SESSION     = str(_VOROVKA_DIR / os.getenv("TG_SESSION_NAME", "sbf_session"))
_API_ID      = int(os.getenv("TG_API_ID", "0"))
_API_HASH    = os.getenv("TG_API_HASH", "")
_CHANNEL     = os.getenv("SBFECONOMICS_CHANNEL", "@SBFEconomics")
_HOURS       = int(os.getenv("BRIEFING_WINDOW_HOURS", "24"))

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

_PROMPT = """Ты — редактор утреннего рыночного обзора SBF. На входе — посты Telegram-канала @SBFEconomics за последние 24 часа. Сделай связную выжимку.

ФОРМАТ ВЫХОДА: только JSON по схеме:
{ "headline": str, "themes": [ {"title": str, "body": str}, ... ], "disclaimer": str }

ПРАВИЛА:
- 3–5 тем (themes), отсортированы по важности. Главный сюжет — первым.
- title: 2–5 слов, суть темы. body: 1–3 предложения связной прозой.
- Только наблюдения и закономерности за сутки. Прошедшее/настоящее время.
- ЗАПРЕЩЕНО: торговые сигналы, рекомендации купить/продать, целевые цены, прогнозы «вырастет/упадёт», гарантии, win-rate, проценты доходности.
- Тикеры упоминать в прозе body, если уместно. НЕ делать отдельный список тикеров.
- НИКАКОЙ разметки в значениях: ни HTML, ни markdown, ни **, ни <strong>. Чистый текст.
- disclaimer: ровно "Аналитическое наблюдение по материалам канала за сутки, не торговая рекомендация."
- Язык: русский.
Верни только JSON, без преамбулы и без ```."""


async def _fetch_posts(hours: int = 24) -> list[str]:
    """Читает текстовые посты @SBFEconomics за последние hours часов."""
    from telethon import TelegramClient

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    posts: list[str] = []

    async with TelegramClient(_SESSION, _API_ID, _API_HASH) as client:
        async for msg in client.iter_messages(_CHANNEL, limit=200):
            if msg.date.replace(tzinfo=timezone.utc) < since:
                break
            if msg.text and len(msg.text.strip()) > 20:
                posts.append(msg.text.strip())

    posts.reverse()   # хронологический порядок
    log.info("fetched %d posts from %s", len(posts), _CHANNEL)
    return posts


def _synthesize(posts: list[str]) -> dict:
    """Вызывает Claude с промптом A.3."""
    import anthropic

    client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    posts_text = "\n\n---\n\n".join(posts[:60])   # ≈ 50k токенов max

    msg = client.messages.create(
        model=os.getenv("BRIEFING_MODEL", "claude-sonnet-4-6"),
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"{_PROMPT}\n\nПОСТЫ КАНАЛА:\n\n{posts_text}",
        }],
    )
    raw = msg.content[0].text.strip()
    # Убираем возможные ``` обёртки
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def run(date: str | None = None) -> bool:
    """Основная точка входа. Возвращает True при успехе."""
    if not _API_ID or not _API_HASH:
        log.error("TG_API_ID / TG_API_HASH не заданы в .env")
        return False
    if not _ANTHROPIC_KEY:
        log.error("ANTHROPIC_API_KEY не задан в .env")
        return False

    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        posts = asyncio.run(_fetch_posts(_HOURS))
    except Exception as e:
        log.error("Telethon fetch failed: %s", e)
        return False

    if not posts:
        log.warning("no posts found in %s for %dh window", _CHANNEL, _HOURS)
        return False

    try:
        payload = _synthesize(posts)
    except Exception as e:
        log.error("Claude synthesis failed: %s", e)
        return False

    payload["date"]          = date
    payload["generated_at"]  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["source_run_id"] = f"sbfe_{date}"

    # Validate minimal schema
    if not payload.get("headline") or not payload.get("themes"):
        log.error("invalid payload from Claude: %s", payload)
        return False

    db.upsert_briefing(
        date=date,
        market="global",
        payload=payload,
        generated_at=payload["generated_at"],
        source_run_id=payload["source_run_id"],
    )
    log.info("briefing generated: %s — %d themes", date, len(payload["themes"]))
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    d = sys.argv[1] if len(sys.argv) > 1 else None
    ok = run(d)
    print("OK" if ok else "FAIL")
