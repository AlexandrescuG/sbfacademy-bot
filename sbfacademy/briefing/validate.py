"""Валидатор структурированного пуша (SPEC_tg_morning_brief_v2.md §4).

По образцу market_intel/analyze/llm_context.py:42-64 -- вызывающая сторона
решает, что делать с невалидным payload'ом (не публикуем аналитическую часть,
не подставляем заглушку). Здесь -- свои правила, по букве §4 спеки, не форма
JSON (форму гарантирует tg_adapt.py), а содержание текста.

Работает на СЫРОМ тексте полей (до HTML-рендера) -- длины видимой/полной
части сообщения (900/3800 знаков, §3/§4) считает уже рендер (render.py),
после того как известна финальная HTML-разметка.
"""
from __future__ import annotations

import re

MAX_LEAD_LEN = 110
MAX_SENTENCE_WORDS = 25

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")

_HEDGE_PHRASES = [
    "в любую сторону", "двустороннее движение", "двустороннего движения",
    "в ту или иную сторону", "или голубиным", "или ястребиным",
]
_HEDGE_LIBO_RE = re.compile(r"\bлибо\b.+\bлибо\b", re.IGNORECASE)

_HISTORICALLY_RE = re.compile(r"исторически|как правило|обычно", re.IGNORECASE)
_HAS_N_RE = re.compile(r"\bn\s*=\s*\d")

_FORECAST_WORDS = ["ожидается", "продолжит", "вырастет", "упадёт", "цель", "прогноз"]
_RECOMMENDATION_WORDS = ["покупать", "продавать", "стоит", "рекомендуем", "лонг", "шорт"]
_RUMOR_LEAK_PHRASES = [
    "по неподтверждённым", "по данным трейдеров",
    "по утверждениям в соцсетях", "непроверяем",
]


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s]


def _check_long_sentences(label: str, text: str, violations: list[str]) -> None:
    for s in _sentences(text):
        n = len(s.split())
        if n > MAX_SENTENCE_WORDS:
            violations.append(f"{label}: предложение длиннее {MAX_SENTENCE_WORDS} слов ({n}): {s!r}")


def _check_hedges(label: str, text: str, violations: list[str]) -> None:
    low = text.lower()
    for phrase in _HEDGE_PHRASES:
        if phrase in low:
            violations.append(f"{label}: симметричная оговорка {phrase!r}: {text!r}")
    if _HEDGE_LIBO_RE.search(low):
        violations.append(f"{label}: конструкция «либо … либо»: {text!r}")


def _check_historically(label: str, text: str, violations: list[str]) -> None:
    for s in _sentences(text):
        if _HISTORICALLY_RE.search(s) and not _HAS_N_RE.search(s):
            violations.append(f"{label}: «исторически»/«как правило»/«обычно» без n=: {s!r}")


def _check_word_list(label: str, text: str, words: list[str], kind: str, violations: list[str]) -> None:
    low = text.lower()
    for w in words:
        if w in low:
            violations.append(f"{label}: {kind} {w!r}: {text!r}")


def _check_rumor_leak(label: str, text: str, violations: list[str]) -> None:
    low = text.lower()
    for phrase in _RUMOR_LEAK_PHRASES:
        if phrase in low:
            violations.append(f"{label}: слух вне блока rumors ({phrase!r}): {text!r}")


def validate_tg_payload(payload: dict) -> list[str]:
    """Список нарушений; пустой список = валидно."""
    violations: list[str] = []

    lead = payload.get("lead") or ""
    if not lead.strip():
        violations.append("lead: пусто")
    else:
        if len(lead) > MAX_LEAD_LEN:
            violations.append(f"lead: длиннее {MAX_LEAD_LEN} знаков ({len(lead)}): {lead!r}")
        if len(_sentences(lead)) > 1:
            violations.append(f"lead: больше одного предложения: {lead!r}")

    # detail/rumors -- содержательные проверки применяются ко всем текстовым
    # полям КРОМЕ rumors (у слухов _RUMOR_LEAK_PHRASES намеренно ожидаемы --
    # это и есть их прямое назначение, помеченное отдельным блоком).
    text_fields: list[tuple[str, str]] = [("lead", lead)]
    for i, d in enumerate(payload.get("detail") or []):
        text_fields.append((f"detail[{i}]", d))
    unknown = payload.get("unknown")
    if unknown:
        text_fields.append(("unknown", unknown))

    for label, text in text_fields:
        _check_long_sentences(label, text, violations)
        _check_hedges(label, text, violations)
        _check_historically(label, text, violations)
        _check_word_list(label, text, _FORECAST_WORDS, "слово прогноза", violations)
        _check_word_list(label, text, _RECOMMENDATION_WORDS, "слово рекомендации", violations)
        _check_rumor_leak(label, text, violations)

    for i, r in enumerate(payload.get("rumors") or []):
        label = f"rumors[{i}]"
        _check_long_sentences(label, r, violations)
        _check_hedges(label, r, violations)
        _check_historically(label, r, violations)
        _check_word_list(label, r, _FORECAST_WORDS, "слово прогноза", violations)
        _check_word_list(label, r, _RECOMMENDATION_WORDS, "слово рекомендации", violations)
        # _check_rumor_leak НЕ применяется к rumors -- это ожидаемое место
        # для таких фраз.

    return violations
