"""Доменные модели — чистый текст, без разметки в данных."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Theme:
    """Один сюжет в брифинге."""
    title: str   # 2–5 слов, чистый текст
    body: str    # 1–3 предложения, чистый текст


@dataclass
class Briefing:
    date: str           # 'YYYY-MM-DD'
    headline: str       # главный сюжет дня, одна строка, чистый текст
    themes: list[Theme] # 3–5 сюжетов
    disclaimer: str
    generated_at: str
    source_run_id: str = ""
    # SPEC_tg_morning_brief_v2.md §2: структурированный payload для нового
    # формата Telegram-пуша (lead/numbers/today/detail/rumors/unknown +
    # "_valid": bool от sbfacademy.briefing.validate). None, если tg_adapt.py
    # не нашёл/не смог собрать данные -- render.py в этом случае падает на
    # легаси-рендер по themes. Аддитивное поле: render_api()/Mini App его не
    # трогают, headline/themes/disclaimer для них не меняются.
    tg: dict | None = None

    def to_dict(self) -> dict:
        return {
            "date":          self.date,
            "headline":      self.headline,
            "themes":        [{"title": t.title, "body": t.body} for t in self.themes],
            "disclaimer":    self.disclaimer,
            "generated_at":  self.generated_at,
            "source_run_id": self.source_run_id,
            "tg":            self.tg,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Briefing":
        themes = [Theme(title=t["title"], body=t["body"]) for t in d.get("themes", [])]

        # Обратная совместимость: старый формат с summary/items → конвертируем
        if not themes and d.get("summary"):
            bullets = [l.strip().lstrip("•").strip()
                       for l in d["summary"].split("\n") if l.strip().startswith("•")]
            for b in bullets[:5]:
                import re
                b = re.sub(r"\*\*([^*]+)\*\*", r"\1", b)
                parts = b.split(":", 1)
                title = parts[0].strip()[:50] if len(parts) > 1 else "Обзор"
                body  = parts[1].strip() if len(parts) > 1 else b
                themes.append(Theme(title=title, body=body))

        return cls(
            date         = d.get("date", ""),
            headline     = d.get("headline", ""),
            themes       = themes,
            disclaimer   = d.get("disclaimer",
                "Аналитическое наблюдение по материалам канала за сутки, не торговая рекомендация."),
            generated_at = d.get("generated_at", ""),
            source_run_id= d.get("source_run_id", ""),
            tg           = d.get("tg"),
        )
