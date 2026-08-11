"""Дневник трейдера: сделки, тезисы, аналитика."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sbfacademy.api.deps import current_user
from sbfacademy.core import db

router = APIRouter(prefix="/api/journal", tags=["journal"])

VALID_DIRECTIONS = {"long", "short"}
VALID_EMOTIONS   = {"calm", "fomo", "fear", "revenge", "tired", "confident", "bored"}
VALID_HORIZONS   = {"1m", "3m", "6m", "1y", "2y"}
VALID_STATUSES   = {"open", "reviewed", "closed"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TradeBody(BaseModel):
    instrument:  Optional[str]   = None
    direction:   Optional[str]   = None
    setup_tag:   Optional[str]   = None
    emotion_tag: Optional[str]   = None
    entry_price: Optional[float] = None
    exit_price:  Optional[float] = None
    size:        Optional[float] = None
    risk_amount: Optional[float] = None
    pnl:         Optional[float] = None
    opened_at:   Optional[str]   = None
    closed_at:   Optional[str]   = None
    notes:       Optional[str]   = None


class ThesisBody(BaseModel):
    instrument:  str
    thesis:      str
    conviction:  int = 3
    horizon:     str = "3m"
    review_date: Optional[str] = None
    status:      Optional[str] = None
    outcome:     Optional[str] = None


class SetupBody(BaseModel):
    name: str


# ── Trades ────────────────────────────────────────────────────────────────────

@router.get("/trades")
async def list_trades(limit: int = 50, offset: int = 0, user: dict = Depends(current_user)):
    db.ensure_default_setups(user["user_id"])
    rows = db.list_trades(user["user_id"], limit=limit, offset=offset)
    return [dict(r) for r in rows]


@router.post("/trades", status_code=201)
async def create_trade(body: TradeBody, user: dict = Depends(current_user)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "direction" in fields and fields["direction"] not in VALID_DIRECTIONS:
        raise HTTPException(400, "direction: long | short")
    if "emotion_tag" in fields and fields["emotion_tag"] not in VALID_EMOTIONS:
        raise HTTPException(400, f"emotion_tag: {sorted(VALID_EMOTIONS)}")
    trade_id = db.create_trade(user["user_id"], **fields)
    db.log_action(user["user_id"], "trade_created", str(trade_id))
    return {"id": trade_id}


@router.put("/trades/{trade_id}")
async def update_trade(trade_id: int, body: TradeBody, user: dict = Depends(current_user)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Нет полей")
    ok = db.update_trade(trade_id, user["user_id"], **fields)
    if not ok:
        raise HTTPException(404, "Сделка не найдена")
    return {"ok": True}


@router.delete("/trades/{trade_id}")
async def delete_trade(trade_id: int, user: dict = Depends(current_user)):
    ok = db.delete_trade(trade_id, user["user_id"])
    if not ok:
        raise HTTPException(404, "Сделка не найдена")
    return {"ok": True}


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(user: dict = Depends(current_user)):
    trades = [dict(r) for r in db.list_all_trades(user["user_id"])]
    return _compute_analytics(trades)


def _compute_analytics(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("pnl") is not None]
    if not closed:
        return {"total": 0, "enough_data": False, "insights": []}

    total     = len(closed)
    wins      = [t for t in closed if t["pnl"] > 0]
    losses    = [t for t in closed if t["pnl"] <= 0]
    winrate   = len(wins) / total

    def safe_avg(lst, key):
        vals = [t[key] for t in lst if t.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    avg_win  = safe_avg(wins, "r_multiple")
    avg_loss = abs(safe_avg(losses, "r_multiple"))
    expectancy = winrate * avg_win - (1 - winrate) * avg_loss

    # Equity curve (cumulative PnL)
    equity, running = [], 0.0
    for t in sorted(closed, key=lambda x: x.get("created_at", "")):
        running += t["pnl"] or 0
        equity.append({"date": t.get("created_at", "")[:10], "pnl": round(running, 2)})

    # Slices
    def slice_stats(key):
        groups: dict[str, list] = {}
        for t in closed:
            val = t.get(key) or "unknown"
            groups.setdefault(val, []).append(t)
        return {
            k: {
                "count": len(v),
                "winrate": round(len([x for x in v if x["pnl"] > 0]) / len(v), 2),
                "avg_r": round(safe_avg(v, "r_multiple"), 2),
            }
            for k, v in groups.items() if len(v) >= 2
        }

    setup_stats   = slice_stats("setup_tag")
    emotion_stats = slice_stats("emotion_tag")

    # Insights (deterministic rules)
    insights = []
    if total >= 10:
        # Revenge trading
        rev = [t for t in closed if t.get("emotion_tag") == "revenge"]
        if rev:
            rev_wr = len([t for t in rev if t["pnl"] > 0]) / len(rev)
            if rev_wr < winrate - 0.1:
                insights.append(
                    f"Сделки на эмоции «отыгрыш» — винрейт {round(rev_wr*100)}% против "
                    f"{round(winrate*100)}% обычного. Серия после убытка влияет на результат."
                )
        # Worst emotion
        for em, st in emotion_stats.items():
            if st["winrate"] < winrate - 0.15 and st["count"] >= 5:
                insights.append(
                    f"Эмоция «{em}»: винрейт {round(st['winrate']*100)}% "
                    f"— заметно хуже среднего ({round(winrate*100)}%)."
                )
                break
        # Best setup
        best = max(setup_stats.items(), key=lambda x: x[1]["winrate"], default=None)
        if best and best[1]["count"] >= 3:
            insights.append(
                f"Сетап «{best[0]}» — лучший результат: "
                f"винрейт {round(best[1]['winrate']*100)}%, avg R {best[1]['avg_r']}."
            )

    return {
        "total":      total,
        "enough_data": total >= 10,
        "winrate":    round(winrate, 3),
        "avg_win_r":  round(avg_win, 2),
        "avg_loss_r": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "equity_curve": equity,
        "by_setup":   setup_stats,
        "by_emotion": emotion_stats,
        "insights":   insights[:3],
    }


# ── Setups ────────────────────────────────────────────────────────────────────

@router.get("/setups")
async def list_setups(user: dict = Depends(current_user)):
    db.ensure_default_setups(user["user_id"])
    return {"setups": db.get_setups(user["user_id"])}


@router.post("/setups", status_code=201)
async def add_setup(body: SetupBody, user: dict = Depends(current_user)):
    name = body.name.strip()[:30]
    if not name:
        raise HTTPException(400, "Имя сетапа не может быть пустым")
    db.add_setup(user["user_id"], name)
    return {"ok": True}


@router.delete("/setups/{name}")
async def delete_setup(name: str, user: dict = Depends(current_user)):
    db.delete_setup(user["user_id"], name)
    return {"ok": True}


# ── Theses ────────────────────────────────────────────────────────────────────

@router.get("/theses")
async def list_theses(status: str | None = None, user: dict = Depends(current_user)):
    rows = db.list_theses(user["user_id"], status=status)
    return [dict(r) for r in rows]


@router.post("/theses", status_code=201)
async def create_thesis(body: ThesisBody, user: dict = Depends(current_user)):
    fields = body.model_dump(exclude_none=True)
    if fields.get("horizon") and fields["horizon"] not in VALID_HORIZONS:
        raise HTTPException(400, f"horizon: {sorted(VALID_HORIZONS)}")
    if not 1 <= fields.get("conviction", 3) <= 5:
        raise HTTPException(400, "conviction: 1..5")
    thesis_id = db.create_thesis(user["user_id"], **fields)
    return {"id": thesis_id}


@router.put("/theses/{thesis_id}")
async def update_thesis(thesis_id: int, body: ThesisBody, user: dict = Depends(current_user)):
    fields = body.model_dump(exclude_none=True)
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        raise HTTPException(400, f"status: {sorted(VALID_STATUSES)}")
    ok = db.update_thesis(thesis_id, user["user_id"], **fields)
    if not ok:
        raise HTTPException(404, "Тезис не найден")
    return {"ok": True}
