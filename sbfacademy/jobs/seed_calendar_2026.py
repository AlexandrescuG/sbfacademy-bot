"""Заполняет econ_events курируемыми датами 2026 из официальных источников.

Источники:
  FOMC  — federalreserve.gov/monetarypolicy/fomccalendars.htm
  CPI   — bls.gov/schedule/news_release/cpi.htm
  NFP   — bls.gov/schedule/news_release/empsit.htm
  PCE   — bea.gov/news/schedule
  GDP   — bea.gov/news/schedule

Запуск:
    python -m sbfacademy.jobs.seed_calendar_2026
"""
from __future__ import annotations

import sys
from pathlib import Path

# .env
from dotenv import load_dotenv
load_dotenv(str(Path(__file__).parent.parent.parent / ".env"))

from sbfacademy.core import db

# Маппинг event title → cheatsheet_id
_CS = {
    "FOMC":          "event_fomc",
    "CPI":           "event_cpi",
    "NFP":           "event_nfp",
    "PCE":           "event_pce",
    "GDP":           "event_gdp",
    "Retail Sales":  "event_retail_sales",
}

def _ev(ts: str, country: str, title: str, impact: str) -> dict:
    slug = title.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")[:20]
    date = ts[:10].replace("-", "")
    cs_id = next((v for k, v in _CS.items() if k.lower() in title.lower()), "")
    yahoo_country = {"US": "united-states", "EU": "euro-zone"}.get(country, "")
    yahoo_url = f"https://finance.yahoo.com/calendar/economic?country={yahoo_country}" if yahoo_country else ""
    return {
        "id":            f"{country.lower()}_{slug}_{date}",
        "ts_utc":        ts,
        "country":       country,
        "title":         title,
        "impact":        impact,
        "actual":        "",
        "forecast":      "",
        "previous":      "",
        "source":        "curated_official",
        "yahoo_url":     yahoo_url,
        "cheatsheet_id": cs_id,
    }


# ── Все события 2026 (оставшиеся с сегодня) ──────────────────────────────────

EVENTS_2026 = [

    # ── FOMC (federalreserve.gov) — объявление в 19:00 UTC ───────────────────
    _ev("2026-07-29T19:00:00Z", "US", "FOMC Rate Decision",  "high"),
    _ev("2026-09-16T19:00:00Z", "US", "FOMC Rate Decision",  "high"),
    _ev("2026-10-28T19:00:00Z", "US", "FOMC Rate Decision",  "high"),
    _ev("2026-12-09T19:00:00Z", "US", "FOMC Rate Decision",  "high"),

    # ── CPI (bls.gov) — 08:30 ET = 13:30 UTC ────────────────────────────────
    _ev("2026-07-15T13:30:00Z", "US", "CPI (June)",          "high"),
    _ev("2026-08-13T13:30:00Z", "US", "CPI (July)",          "high"),
    _ev("2026-09-10T13:30:00Z", "US", "CPI (August)",        "high"),
    _ev("2026-10-14T13:30:00Z", "US", "CPI (September)",     "high"),
    _ev("2026-11-12T13:30:00Z", "US", "CPI (October)",       "high"),
    _ev("2026-12-10T13:30:00Z", "US", "CPI (November)",      "high"),

    # ── NFP / Nonfarm Payrolls (bls.gov) — первая пятница, 08:30 ET ─────────
    _ev("2026-07-02T13:30:00Z", "US", "NFP (June)",          "high"),
    _ev("2026-08-07T13:30:00Z", "US", "NFP (July)",          "high"),
    _ev("2026-09-04T13:30:00Z", "US", "NFP (August)",        "high"),
    _ev("2026-10-02T13:30:00Z", "US", "NFP (September)",     "high"),
    _ev("2026-11-06T13:30:00Z", "US", "NFP (October)",       "high"),
    _ev("2026-12-04T13:30:00Z", "US", "NFP (November)",      "high"),

    # ── PCE (bea.gov) — конец месяца, 08:30 ET ──────────────────────────────
    _ev("2026-07-31T13:30:00Z", "US", "PCE (June)",          "high"),
    _ev("2026-08-28T13:30:00Z", "US", "PCE (July)",          "high"),
    _ev("2026-09-25T13:30:00Z", "US", "PCE (August)",        "high"),
    _ev("2026-10-30T13:30:00Z", "US", "PCE (September)",     "high"),
    _ev("2026-11-25T13:30:00Z", "US", "PCE (October)",       "high"),
    _ev("2026-12-18T13:30:00Z", "US", "PCE (November)",      "high"),

    # ── GDP Advance Estimate (bea.gov) — ~4 нед. после конца квартала ───────
    _ev("2026-07-29T13:30:00Z", "US", "GDP Q2 2026 (Advance)", "high"),
    _ev("2026-10-28T13:30:00Z", "US", "GDP Q3 2026 (Advance)", "high"),

    # ── Retail Sales (census.gov) — ~2 нед. после месяца, 08:30 ET ──────────
    _ev("2026-07-16T13:30:00Z", "US", "Retail Sales (June)",    "medium"),
    _ev("2026-08-14T13:30:00Z", "US", "Retail Sales (July)",    "medium"),
    _ev("2026-09-11T13:30:00Z", "US", "Retail Sales (August)",  "medium"),
    _ev("2026-10-15T13:30:00Z", "US", "Retail Sales (September)", "medium"),
    _ev("2026-11-13T13:30:00Z", "US", "Retail Sales (October)",  "medium"),
    _ev("2026-12-11T13:30:00Z", "US", "Retail Sales (November)", "medium"),
]


def seed() -> int:
    db.init_db()
    for ev in EVENTS_2026:
        db.upsert_econ_event(ev)
    print(f"Seeded {len(EVENTS_2026)} events into econ_events.")
    return len(EVENTS_2026)


if __name__ == "__main__":
    n = seed()
    sys.exit(0 if n else 1)
