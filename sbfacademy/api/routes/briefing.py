from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sbfacademy.api.deps import current_user
from sbfacademy.briefing import store
from sbfacademy.core import db
from datetime import datetime, timezone

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


@router.get("/today/teaser")
async def today_teaser():
    """Публичный тизер без авторизации: headline + первая тема."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    briefing = store.get_by_date(date)
    if not briefing:
        rows = store.list_archive(limit=1)
        if not rows:
            raise HTTPException(204, "Брифинг ещё не готов")
        briefing = store.get_by_date(rows[0]["date"])
        date = rows[0]["date"]
    if not briefing:
        raise HTTPException(204, "Брифинг ещё не готов")
    first = briefing.themes[0] if briefing.themes else None
    return {
        "date":        date,
        "headline":    briefing.headline,
        "first_theme": {"title": first.title, "body": first.body} if first else {},
    }


@router.get("/today")
async def today(user: dict = Depends(current_user)):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    briefing = store.get_for_user(user["user_id"], date)
    if not briefing:
        raise HTTPException(204, "Брифинг ещё не готов")
    db.log_action(user["user_id"], "briefing_opened", date)
    from sbfacademy.briefing.render import render_api
    return render_api(briefing, user)


@router.get("/archive")
async def archive(user: dict = Depends(current_user), limit: int = 30):
    return store.list_archive(limit)


@router.get("/{date}")
async def by_date(date: str, user: dict = Depends(current_user)):
    briefing = store.get_by_date(date)
    if not briefing:
        raise HTTPException(404, "Брифинг не найден")
    db.log_action(user["user_id"], "archive_viewed", date)
    from sbfacademy.briefing.render import render_api
    return render_api(briefing, user)
