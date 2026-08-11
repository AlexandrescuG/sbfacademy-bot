from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, Depends
from sbfacademy.api.deps import current_user

router = APIRouter(prefix="/api/markets", tags=["markets"])

_MARKETS_PATH = Path(__file__).parent.parent.parent / "content" / "markets.json"


@lru_cache(maxsize=1)
def _load_markets() -> list[dict]:
    return json.loads(_MARKETS_PATH.read_text(encoding="utf-8"))


@router.get("")
async def list_markets(user: dict = Depends(current_user)):
    return {"markets": _load_markets()}
