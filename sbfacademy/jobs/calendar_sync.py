"""Синхронизация экономического календаря с Finnhub.

Запуск:
    python -m sbfacademy.jobs.calendar_sync          # синхронизирует текущую неделю
    python -m sbfacademy.jobs.calendar_sync 2026-07-01 2026-07-07
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent.parent.parent / ".env"))

from sbfacademy.core import db

log = logging.getLogger("sbfacademy.jobs.calendar_sync")

_FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

# Маппинг Finnhub event → cheatsheet_id
_EVENT_CHEATSHEET = {
    "FOMC":           "evt_fomc",
    "CPI":            "evt_cpi",
    "NFP":            "evt_nfp",
    "Non-Farm":       "evt_nfp",
    "PCE":            "evt_pce",
    "GDP":            "evt_gdp",
    "OPEC":           "evt_opec",
    "Retail Sales":   "evt_retail_sales",
    "Earnings":       "evt_earnings",
}

# Маппинг страна Finnhub → Yahoo Finance country tag для дип-линков
_YAHOO_COUNTRY = {
    "US": "united-states",
    "EU": "euro-zone",
    "GB": "united-kingdom",
    "CN": "china",
    "JP": "japan",
    "CA": "canada",
    "AU": "australia",
}


def _make_event_id(ev: dict) -> str:
    date = ev.get("time", "")[:10].replace("-", "")
    country = ev.get("country", "xx").lower()
    slug = ev.get("event", "").lower()[:20].replace(" ", "_").replace("/", "_")
    return f"{country}_{slug}_{date}"


def _cheatsheet_for(title: str) -> str:
    for kw, cs_id in _EVENT_CHEATSHEET.items():
        if kw.lower() in title.lower():
            return cs_id
    return ""


def _yahoo_url(ev: dict) -> str:
    country = _YAHOO_COUNTRY.get(ev.get("country", ""), "")
    if country:
        return f"https://finance.yahoo.com/calendar/economic?country={country}"
    return "https://finance.yahoo.com/calendar/economic"


def sync(date_from: str, date_to: str) -> int:
    if not _FINNHUB_KEY:
        log.error("FINNHUB_API_KEY не задан в .env")
        return 0

    try:
        import requests
    except ImportError:
        log.error("requests не установлен: pip install requests")
        return 0

    url = "https://finnhub.io/api/v1/calendar/economic"
    r = requests.get(url, params={"from": date_from, "to": date_to},
                     headers={"X-Finnhub-Token": _FINNHUB_KEY}, timeout=15)
    r.raise_for_status()
    data = r.json()

    events = data.get("economicCalendar", [])
    count = 0
    for ev in events:
        try:
            event = {
                "id":            _make_event_id(ev),
                "ts_utc":        ev.get("time", ""),
                "country":       ev.get("country", ""),
                "title":         ev.get("event", ""),
                "impact":        ev.get("impact", "low"),
                "actual":        str(ev.get("actual", "")) if ev.get("actual") is not None else "",
                "forecast":      str(ev.get("estimate", "")) if ev.get("estimate") is not None else "",
                "previous":      str(ev.get("prev", "")) if ev.get("prev") is not None else "",
                "source":        "finnhub",
                "yahoo_url":     _yahoo_url(ev),
                "cheatsheet_id": _cheatsheet_for(ev.get("event", "")),
            }
            db.upsert_econ_event(event)
            count += 1
        except Exception as e:
            log.warning("skip event %s: %s", ev.get("event"), e)

    log.info("synced %d events (%s → %s)", count, date_from, date_to)
    return count


async def calendar_sync_job(context) -> None:
    """PTB JobQueue callback — ежедневная синхронизация."""
    now = datetime.now(timezone.utc)
    date_from = now.strftime("%Y-%m-%d")
    date_to   = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    count = sync(date_from, date_to)
    log.info("calendar_sync_job: %d events", count)

    # Отправить FCM-алерты
    _send_due_alerts(context)


def _send_due_alerts(context) -> None:
    try:
        due = db.get_due_econ_alerts(window_minutes=5)
        for alert in due:
            title_text = f"📅 {alert['title']} через {alert['lead_minutes']} мин"
            body_text  = f"{alert['country']} · {alert['impact'].upper()} impact"
            try:
                from sbfacademy.api.fcm import send_push
                from sbfacademy.core.db import get_fcm_tokens
                for token in get_fcm_tokens(alert["user_id"]):
                    send_push(token, title_text, body_text, {"type": "econ_alert", "event_id": alert["event_id"]})
            except Exception as e:
                log.warning("FCM alert failed user=%d: %s", alert["user_id"], e)
    except Exception as e:
        log.error("_send_due_alerts: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    if len(sys.argv) == 3:
        d_from, d_to = sys.argv[1], sys.argv[2]
    else:
        now = datetime.now(timezone.utc)
        d_from = now.strftime("%Y-%m-%d")
        d_to   = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    n = sync(d_from, d_to)
    print(f"Synced {n} events")
