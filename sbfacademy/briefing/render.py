"""Рендер брифинга. Данные — чистый текст. Разметка только здесь."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from sbfacademy.core.config import SITE_URL
from sbfacademy.core.models import Briefing

# SPEC_tg_morning_brief_v2.md §3/§4.
VISIBLE_LIMIT = 900   # видимая часть до раскрытия
TOTAL_LIMIT = 3800    # запас от жёсткого лимита Telegram 4096

_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _fmt_date(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        MONTHS = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
        return f"{d.day} {MONTHS[d.month - 1]}"
    except Exception:
        return iso


def _esc(text: str) -> str:
    """HTML-экранирование, затем **markdown-жирный** -> <b>. В этом порядке --
    экранирование не трогает `*`, поэтому разметка компонуется уже поверх
    экранированного текста, а не наоборот (иначе получившиеся <b>/</b> сами
    попали бы под escape)."""
    return _BOLD_RE.sub(r"<b>\1</b>", html.escape(text or ""))


def _keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Полный обзор →", url=SITE_URL),
        InlineKeyboardButton("Календарь", url=f"{SITE_URL}/calendar"),
    ]])


def _numbers_block(numbers: list[dict]) -> str:
    if not numbers:
        return ""
    name_w = max(len(n["name"]) for n in numbers)
    chg_w = max(len(n["chg"]) for n in numbers)
    lines = []
    for n in numbers:
        row = f"{n['name'].ljust(name_w)}  {n['chg'].rjust(chg_w)}  {n['level']}"
        if n.get("note"):
            row += f"   {n['note']}"
        lines.append(row)
    return "<pre>" + html.escape("\n".join(lines)) + "</pre>"


def _local_time(ts_utc: str | None, user_tz: str) -> str:
    if not ts_utc:
        return "--:--"
    try:
        dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        local = dt.astimezone(ZoneInfo(user_tz))
        return local.strftime("%H:%M")
    except Exception:
        return "--:--"


def _today_lines(today: list[dict], user_tz: str) -> list[str]:
    lines = []
    for e in today:
        t = _local_time(e.get("ts_utc"), user_tz)
        what = _esc(e.get("what") or "")
        symbols = e.get("symbols") or []
        suffix = f" ({', '.join(symbols)})" if symbols else ""
        lines.append(f"{t} — {what}{suffix}")
    return lines


def _render_full(briefing: Briefing, user_tz: str) -> str:
    tg = briefing.tg
    lines = [f"📊 <b>{_fmt_date(briefing.date)}</b>", ""]
    lines.append(_esc(tg["lead"]))

    numbers_block = _numbers_block(tg.get("numbers") or [])
    if numbers_block:
        lines += ["", numbers_block]

    today_lines = _today_lines(tg.get("today") or [], user_tz)
    if today_lines:
        lines += [""] + today_lines

    if tg.get("unknown"):
        lines += ["", _esc(tg["unknown"])]

    detail_rumors: list[str] = []
    for d in tg.get("detail") or []:
        detail_rumors.append(_esc(d))
    for r in tg.get("rumors") or []:
        detail_rumors.append("⚠️ Непроверено: " + _esc(r))
    if detail_rumors:
        inner = "\n\n".join(detail_rumors)
        lines += ["", f"<blockquote expandable>{inner}</blockquote>"]

    lines += ["", f"<i>{html.escape(briefing.disclaimer)}</i>"]
    return "\n".join(lines)


def _render_reduced(briefing: Briefing, user_tz: str) -> str:
    """SPEC §4: провалил валидатор/превысил лимит длины -- только числа и
    календарь (машинные данные, всегда корректны), без раскрытия анализа."""
    tg = briefing.tg
    lines = [f"📊 <b>{_fmt_date(briefing.date)}</b>", ""]

    numbers_block = _numbers_block(tg.get("numbers") or [])
    if numbers_block:
        lines.append(numbers_block)

    today_lines = _today_lines(tg.get("today") or [], user_tz)
    if today_lines:
        lines += [""] + today_lines

    lines += ["", "Аналитическая часть сегодня не прошла проверку."]
    lines += ["", f"<i>{html.escape(briefing.disclaimer)}</i>"]
    return "\n".join(lines)


def _render_legacy(briefing: Briefing) -> str:
    lines = [f"📊 <b>Утренний обзор · {_fmt_date(briefing.date)}</b>", ""]
    lines.append(briefing.headline)
    lines.append("")
    for theme in briefing.themes:
        lines.append(f"<b>{theme.title}</b>")
        lines.append(theme.body)
        lines.append("")
    lines.append(f"<i>{briefing.disclaimer}</i>")
    return "\n".join(lines)


def _visible_len(text: str) -> int:
    """Длина части ДО <blockquote expandable> -- это то, что видно на экране
    без раскрытия (SPEC §3 "до 900 знаков")."""
    idx = text.find("<blockquote")
    return len(text) if idx == -1 else idx


def render_push(briefing: Briefing, user_tz: str = "UTC") -> tuple[str, InlineKeyboardMarkup]:
    """Telegram HTML — parse_mode='HTML'. Три ветки по briefing.tg:
    полный формат (валиден) / сокращённый (провалил валидацию) / легаси
    (структурированного payload нет вовсе — старый формат по themes)."""
    if briefing.tg is None:
        return _render_legacy(briefing), _keyboard()

    if briefing.tg.get("_valid"):
        text = _render_full(briefing, user_tz)
        # Вторая линия защиты сверх валидатора на этапе ingest (SPEC §4):
        # контент был чист по содержанию, но после рендера (например,
        # необычно длинный список numbers/today) вышел за бюджет длины --
        # падаем в сокращённый рендер, а не полагаемся на TG_LIMIT-нарезку.
        if _visible_len(text) <= VISIBLE_LIMIT and len(text) <= TOTAL_LIMIT:
            return text, _keyboard()

    return _render_reduced(briefing, user_tz), _keyboard()


def render_api(briefing: Briefing, user: dict | None = None) -> dict:
    """JSON для Mini App — webapp сам форматирует через CSS."""
    return briefing.to_dict()
