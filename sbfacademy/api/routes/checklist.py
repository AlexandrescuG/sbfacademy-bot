"""Чек-лист перед сделкой."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sbfacademy.api.deps import current_user
from sbfacademy.core import db

router = APIRouter(prefix="/api/checklist", tags=["checklist"])


class RunBody(BaseModel):
    answers: dict          # {item_id: bool}
    trade_id: Optional[int] = None


class ItemUpdateBody(BaseModel):
    text:     Optional[str] = None
    enabled:  Optional[int] = None
    position: Optional[int] = None


@router.get("/items")
async def get_items(user: dict = Depends(current_user)):
    db.ensure_default_checklist(user["user_id"])
    rows = db.get_checklist(user["user_id"])
    return [dict(r) for r in rows]


@router.put("/items/{item_id}")
async def update_item(item_id: int, body: ItemUpdateBody, user: dict = Depends(current_user)):
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "Нет полей")
    ok = db.update_checklist_item(user["user_id"], item_id, **fields)
    if not ok:
        raise HTTPException(404, "Пункт не найден")
    return {"ok": True}


@router.post("/run", status_code=201)
async def save_run(body: RunBody, user: dict = Depends(current_user)):
    run_id = db.save_checklist_run(user["user_id"], body.answers, body.trade_id)
    db.log_action(user["user_id"], "checklist_run", str(run_id))
    all_ok = all(body.answers.values())
    return {"id": run_id, "all_checked": all_ok}
