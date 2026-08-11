"""Шпаргалки: офлайн-справочник с поиском."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sbfacademy.api.deps import current_user
from sbfacademy.core import db

router = APIRouter(prefix="/api/cheatsheets", tags=["cheatsheets"])

VALID_CATEGORIES = {"indicator", "chart_pattern", "candle_pattern", "event", "risk"}


@router.get("")
async def list_cheatsheets(
    q: str = "",
    category: str = "",
    user: dict = Depends(current_user),
):
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(400, f"category: {sorted(VALID_CATEGORIES)}")
    rows = db.search_cheatsheets(q=q, category=category)
    return [dict(r) for r in rows]


@router.get("/{sheet_id}")
async def get_cheatsheet(sheet_id: str, user: dict = Depends(current_user)):
    row = db.get_cheatsheet(sheet_id)
    if not row:
        raise HTTPException(404, "Карточка не найдена")
    return dict(row)
