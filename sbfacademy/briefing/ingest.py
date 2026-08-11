"""Адаптер market_intel → briefings.

Читает data/reports/report_YYYY-MM-DD.md, нормализует в контракт Briefing,
пишет в таблицу briefings (upsert). Безопасно вызывать повторно.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sbfacademy.briefing import tg_adapt, validate
from sbfacademy.core import db
from sbfacademy.core.config import MARKET_INTEL_REPORT_DIR
from sbfacademy.core.models import Briefing, Theme

log = logging.getLogger("sbfacademy.briefing.ingest")


_SECTION_RE = re.compile(r"^##\s*(.+?)\s*\n([\s\S]+?)(?=\n##\s|\Z)", re.MULTILINE)
_BULLET_RE  = re.compile(r"^-\s+(.+)", re.MULTILINE)
_BOLD_RE    = re.compile(r"\*+([^*]+)\*+")
_EMOJI_RE   = re.compile(r"^[^\wа-яёА-ЯЁ]+")


def _strip_bold(s: str) -> str:
    return _BOLD_RE.sub(r"\1", s).strip()


def _parse_heatmap(text: str) -> list[tuple[str, int, str]]:
    """Парсит тепловую карту тикеров — поддерживает формат таблицы И bullet-list."""
    section = None

    # Формат 1: ## / ### Тепловая карта ...
    m = re.search(
        r"#{2,3}[^\n]*тепловая карта[^\n]*\n([\s\S]+?)(?=\n#{2,3}|\n---|\Z)",
        text, re.IGNORECASE,
    )
    if m:
        section = m.group(1)

    # Формат 2: **Тикеры в центре внимания (тепловая карта)**:
    if not section:
        m = re.search(
            r"\*\*[^*]*тепловая карта[^*]*\*\*[^\n]*\n([\s\S]+?)(?=\n###|\n##|\n---|\n\*\*[А-ЯA-Z]|\Z)",
            text, re.IGNORECASE,
        )
        if m:
            section = m.group(1)

    if not section:
        return []

    # Попытка 1: таблица | $SPY | 59× | 0.33 | note |
    table_rows = re.findall(
        r"\|\s*(\$\w+)\s*\|\s*(\d+)[×xх]\s*\|\s*[^|]*\|\s*([^|\n]+)", section
    )
    if table_rows:
        result = [(a.lstrip("$"), int(c), n.strip()) for a, c, n in table_rows]
        result.sort(key=lambda x: x[1], reverse=True)
        return result[:6]

    # Попытка 2: bullet-list  - $SPY (30×), $QQQ (21×) — описание
    all_tickers: list[tuple[str, int, str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        desc_m = re.search(r"[—–]\s*(.+)", stripped)
        note = desc_m.group(1).strip() if desc_m else ""
        for ticker, count in re.findall(r"\$(\w+)\s*\((\d+)[×xх]\)", stripped):
            all_tickers.append((ticker, int(count), note))

    all_tickers.sort(key=lambda x: x[1], reverse=True)
    return all_tickers[:6]


def _report_path(date: str) -> Path:
    return MARKET_INTEL_REPORT_DIR / f"report_{date}.md"


def _parse_report(text: str, date: str) -> Briefing:
    """Извлекает headline и themes из Markdown-отчёта market_intel.

    Раньше парсер искал разделы по точному тексту заголовка (## ⚡ TL;DR,
    ## 🎯 Что это значит...) и брал только первые 5 буллетов TL;DR + до 600
    символов из одного раздела — «Геополитика», «Экономика», «Сознание
    толпы» вообще не попадали в Mini App. Названия заголовков в отчёте с тех
    пор сменились (TL;DR → Краткое содержание), regex перестал совпадать
    вовсе. Теперь берём КАЖДЫЙ ## -раздел целиком, независимо от его
    названия — переживёт будущие переименования разделов в market_intel.

    Раздел без `- ` маркеров (модель написала прозой) раньше отбрасывался
    целиком (`if not bullets: continue`) — 29.07 так потерялись 4 из 5
    разделов одного выпуска. Теперь такой раздел не пропускается: весь его
    текст берётся одним "буллетом".
    """
    headline = ""
    themes: list[Theme] = []
    for title, body in _SECTION_RE.findall(text):
        clean_title = _EMOJI_RE.sub("", title).strip()
        bullets = _BULLET_RE.findall(body)
        if not bullets:
            prose = body.strip()
            if not prose:
                continue
            bullets = [prose]
        clean_bullets = [_strip_bold(b) for b in bullets]
        if not headline:
            headline = clean_bullets[0]
            clean_bullets = clean_bullets[1:]
        if clean_bullets:
            themes.append(Theme(title=clean_title[:60], body="\n\n".join(clean_bullets)[:6000]))

    # ── тикеры из тепловой карты → доп. тема ──────────────────────────────────
    ticker_data = _parse_heatmap(text)
    if ticker_data:
        tickers_body = ", ".join(
            f"${a} ({n or f'{c}×'})" for a, c, n in ticker_data[:5]
        )
        themes.append(Theme(title="Тикеры в фокусе", body=tickers_body))

    if not headline:
        headline = f"Рыночный обзор · {date}"
    if not themes:
        themes = [Theme(title="Обзор", body="Данные недоступны.")]

    return Briefing(
        date=date,
        headline=headline,
        themes=themes,
        disclaimer="Аналитическое наблюдение, не торговая рекомендация.",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_run_id=f"mi_{date}_global",
    )


def run(date: str | None = None) -> bool:
    """Читает отчёт за дату (default=сегодня), пишет в briefings. Возвращает True при успехе."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = _report_path(date)
    if not path.exists():
        log.warning("report not found: %s", path)
        return False
    text = path.read_text(encoding="utf-8")
    briefing = _parse_report(text, date)

    # SPEC_tg_morning_brief_v2.md §2/§4: собираем структурированный payload для
    # нового формата Telegram-пуша из уже посчитанного market_intel-пайплайна
    # (brief_today.json) -- не новый LLM-вызов, чистый маппинг. Валидация -- один
    # раз в день здесь (не на каждой отправке в send_briefing), одна строка в
    # лог с полным контекстом при провале, как просит §4.
    tg_payload = tg_adapt.build_tg_payload(date)
    if tg_payload is not None:
        violations = validate.validate_tg_payload(tg_payload)
        tg_payload["_valid"] = not violations
        if violations:
            log.warning("tg payload rejected for %s: %s | payload=%r", date, violations, tg_payload)
        briefing.tg = tg_payload

    db.upsert_briefing(
        date=briefing.date,
        market="global",
        payload=briefing.to_dict(),
        generated_at=briefing.generated_at,
        source_run_id=briefing.source_run_id,
    )
    log.info("briefing ingested: date=%s themes=%d", date, len(briefing.themes))
    return True


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    d = sys.argv[1] if len(sys.argv) > 1 else None
    ok = run(d)
    print("OK" if ok else "FAIL — report not found")
