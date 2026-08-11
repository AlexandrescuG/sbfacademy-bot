"""Экономический календарь: события + FCM-алерты."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sbfacademy.api.deps import current_user
from sbfacademy.core import db

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

VALID_IMPACT = {"high", "medium", "low"}


class AlertBody(BaseModel):
    event_id:     str
    lead_minutes: int = 60


@router.get("/events")
async def list_events(
    date:    Optional[str] = None,
    impact:  Optional[str] = None,
    country: Optional[str] = None,
    user: dict = Depends(current_user),
):
    if impact and impact not in VALID_IMPACT:
        raise HTTPException(400, f"impact: {sorted(VALID_IMPACT)}")
    rows = db.list_econ_events(date=date, impact=impact, country=country)
    return [dict(r) for r in rows]


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(current_user)):
    row = db.get_econ_event(event_id)
    if not row:
        raise HTTPException(404, "Событие не найдено")
    return dict(row)


@router.get("/alerts")
async def get_alerts(user: dict = Depends(current_user)):
    rows = db.get_user_econ_alerts(user["user_id"])
    return [dict(r) for r in rows]


@router.post("/alerts", status_code=201)
async def set_alert(body: AlertBody, user: dict = Depends(current_user)):
    if not (1 <= body.lead_minutes <= 1440):
        raise HTTPException(400, "lead_minutes: 1..1440")
    if not db.get_econ_event(body.event_id):
        raise HTTPException(404, "Событие не найдено")
    db.set_econ_alert(user["user_id"], body.event_id, body.lead_minutes)
    return {"ok": True}


@router.delete("/alerts/{event_id}")
async def delete_alert(event_id: str, user: dict = Depends(current_user)):
    db.delete_econ_alert(user["user_id"], event_id)
    return {"ok": True}
