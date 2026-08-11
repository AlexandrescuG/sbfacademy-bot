"""Выборка брифинга — глобальный, без сегментации рынков."""
from __future__ import annotations
from datetime import datetime, timezone
from sbfacademy.core import db
from sbfacademy.core.models import Briefing


def get_today() -> Briefing | None:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_by_date(date)


def get_for_user(user_id: int, date: str | None = None) -> Briefing | None:
    """Обратная совместимость с push.py — возвращает глобальный брифинг."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_by_date(date)


def get_by_date(date: str) -> Briefing | None:
    payload = db.get_briefing(date, "global")
    return Briefing.from_dict(payload) if payload else None


def list_archive(limit: int = 30) -> list[dict]:
    """Список {date, headline} для экрана истории."""
    rows = db.list_briefings("global", limit)
    return [{"date": r["date"], "headline": r["headline"]} for r in rows]
