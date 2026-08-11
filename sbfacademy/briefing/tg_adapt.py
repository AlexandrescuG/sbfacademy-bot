"""Адаптер market_intel → Telegram-пуш (SPEC_tg_morning_brief_v2.md §2).

Никакого нового LLM-вызова: рынок_intel уже строит детерминированный
web/data/brief_today.json (build_brief_v2.py — реальные календарь/движения/
паттерны, без LLM) и мерджит в него headline+context+unknown (llm_context.py —
модель пишет всего 4-5 полей, Python валидирует). Этот файл — чистый Python,
маппинг уже посчитанных реальных данных в схему §2, не генерация контента.
"""
from __future__ import annotations

import json
import logging

from sbfacademy.core.config import MARKET_INTEL_WEB_DATA_DIR

log = logging.getLogger("sbfacademy.briefing.tg_adapt")

NUMBERS_CAP = 5
TODAY_CAP = 3
RUMORS_CAP = 2
RATIO_NOTE_THRESHOLD = 1.3

# Зеркалит market_intel/analyze/prompt.md — тот же словарь тикеров, которым
# пользуется LLM-отчёт, чтобы блок чисел не расходился по терминологии.
_TICKER_RU = {
    "GOLD": "Золото", "SILVER": "Серебро", "BTC": "Биткоин", "ETH": "Эфириум",
    "SOL": "Солана", "EURUSD": "Евро/доллар", "GBPUSD": "Фунт/доллар",
    "SPX": "S&P 500", "NASDAQ": "Nasdaq", "DJI": "Dow Jones",
    "WTI": "Нефть WTI", "NG": "Природный газ", "DXY": "Индекс доллара",
    "USDJPY": "Доллар/иена", "USDRUB": "Доллар/рубль", "USDKZT": "Доллар/тенге",
}


def _ticker_name(symbol: str) -> str:
    return _TICKER_RU.get(symbol, symbol)


def _fmt_chg(chg_pct: float) -> str:
    # Проектная конвенция для отрицательных чисел в RU-тексте -- типографский
    # минус (U+2212), не ASCII-дефис (market_intel/analyze/prompt.md:99).
    s = f"{chg_pct:+.1f}%".replace(".", ",")
    return s.replace("-", "−", 1) if s.startswith("-") else s


def _fmt_level(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}".replace(",", " ")
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return (s.replace(".", ",") or "0")


def _mover_note(m: dict) -> str:
    ratio = m.get("ratio")
    if isinstance(ratio, (int, float)) and ratio >= RATIO_NOTE_THRESHOLD:
        return f"×{ratio:.1f} нормы".replace(".", ",")
    event = m.get("event")
    if event and event.get("title"):
        words = event["title"].split()[:4]
        return " ".join(words)
    return ""


def _build_numbers(movers: dict) -> list[dict]:
    rows = list(movers.get("up", [])) + list(movers.get("down", []))
    rows.sort(key=lambda m: m.get("ratio") or 0, reverse=True)
    out = []
    for m in rows[:NUMBERS_CAP]:
        out.append({
            "name": _ticker_name(m["symbol"]),
            "chg": _fmt_chg(m["chg_pct"]),
            "level": _fmt_level(m["close"]),
            "note": _mover_note(m),
        })
    return out


def _build_today(calendar: list[dict]) -> list[dict]:
    # high раньше medium (значимость), внутри группы — как отдала build_calendar_block
    # (уже отсортировано по времени).
    ranked = sorted(calendar, key=lambda e: 0 if e.get("impact") == "high" else 1)
    out = []
    for e in ranked[:TODAY_CAP]:
        out.append({
            "ts_utc": e.get("ts_utc"),   # локализуется на этапе рендера, не здесь
            "what": e.get("title") or e.get("indicator") or "",
            "symbols": e.get("symbols") or [],
        })
    return out


def _build_detail_rumors(context: list[dict]) -> tuple[list[str], list[str]]:
    detail = [c["text"] for c in context if c.get("confidence") in ("quotes", "media")]
    rumors = [c["text"] for c in context if c.get("confidence") == "social_unverified"][:RUMORS_CAP]
    return detail, rumors


def build_tg_payload(date: str) -> dict | None:
    """None, если файла нет / не парсится / дата не совпадает (протухшие данные) --
    вызывающий код (ingest.py) просто не публикует briefing.tg в этом случае,
    легаси-рендер остаётся рабочим fallback'ом."""
    path = MARKET_INTEL_WEB_DATA_DIR / "brief_today.json"
    if not path.exists():
        log.warning("tg_adapt: %s не существует", path)
        return None
    try:
        brief = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("tg_adapt: не удалось прочитать %s: %s", path, e)
        return None

    if brief.get("date") != date:
        log.warning("tg_adapt: brief_today.json датирован %s, ожидали %s -- протухшие данные",
                    brief.get("date"), date)
        return None

    headline = brief.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        # headline/context не смержены (llm_context.py упал/не нашёл файл) --
        # у нас нет lead без него, структурированный пуш собрать нельзя.
        return None

    detail, rumors = _build_detail_rumors(brief.get("context") or [])

    return {
        "lead": headline.strip(),
        "numbers": _build_numbers(brief.get("movers") or {}),
        "today": _build_today(brief.get("calendar") or []),
        "detail": detail,
        "rumors": rumors,
        "unknown": brief.get("unknown"),
    }
