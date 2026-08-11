from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sbfacademy.api.deps import current_user
from sbfacademy.core import db

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistBody(BaseModel):
    assets: list[str]


@router.get("")
async def get_watchlist(user: dict = Depends(current_user)):
    items = db.get_watchlist(user["user_id"])
    return {"assets": items}


@router.put("")
async def set_watchlist(body: WatchlistBody, user: dict = Depends(current_user)):
    if len(body.assets) > 20:
        raise HTTPException(400, "Максимум 20 активов в watchlist")
    db.set_watchlist(user["user_id"], body.assets)
    return {"assets": body.assets}
