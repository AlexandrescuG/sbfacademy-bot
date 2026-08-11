"""Заполняет БД seed-данными (шпаргалки). Идемпотентно — INSERT OR IGNORE."""
from __future__ import annotations

import json
from pathlib import Path

from sbfacademy.core import db

_DATA_DIR = Path(__file__).parent


def seed_all() -> None:
    db.init_db()
    _seed_cheatsheets()
    print("Seed complete.")


def _seed_cheatsheets() -> None:
    cards = json.loads((_DATA_DIR / "cheatsheets.json").read_text(encoding="utf-8"))
    db.seed_cheatsheets(cards)
    print(f"  cheatsheets: {len(cards)} cards seeded")


if __name__ == "__main__":
    seed_all()
