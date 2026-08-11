"""Загрузка конфигурации из .env. Единственный источник истины для всего модуля."""
import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
MANAGER_CHAT_ID  = int(os.getenv("MANAGER_CHAT_ID", "0"))
LEADS_CHANNEL_ID = int(os.getenv("LEADS_CHANNEL_ID", "0"))
ADMIN_IDS        = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
OPERATOR_IDS     = [int(x) for x in os.getenv("OPERATOR_IDS", "").split(",") if x.strip()]

# ── crm — SBFCRM (JWT Bearer) ────────────────────────────────────────────────
SBFCRM_URL      = os.getenv("SBFCRM_URL", "https://web.sbfconsult.com")
SBFCRM_EMAIL    = os.getenv("SBFCRM_EMAIL", "")
SBFCRM_PASSWORD = os.getenv("SBFCRM_PASSWORD", "")

# ── db / paths ────────────────────────────────────────────────────────────────
_BOT_DIR = Path(__file__).parent.parent.parent   # .../SBFAcademy_bot/
DB_PATH  = Path(os.getenv("DB_PATH", str(_BOT_DIR / "bot.db")))

MARKET_INTEL_REPORT_DIR = Path(
    os.getenv("MARKET_INTEL_REPORT_DIR", "/home/sbf/market_intel/data/reports")
)

# ── briefing schedule ─────────────────────────────────────────────────────────
# UTC-час запуска ingest (после того как market_intel досчитал)
BRIEFING_INGEST_HOUR   = int(os.getenv("BRIEFING_INGEST_HOUR", "10"))
BRIEFING_INGEST_MINUTE = int(os.getenv("BRIEFING_INGEST_MINUTE", "15"))

MARKET_INTEL_WEB_DATA_DIR = Path(
    os.getenv("MARKET_INTEL_WEB_DATA_DIR", "/home/sbf/market_intel/web/data")
)

# SPEC_tg_morning_brief_v2.md §0.4/§5: замена дефолта 'Asia/Almaty' (не подошёл
# для молдавской аудитории) на единый дефолт часового пояса для всего проекта.
DEFAULT_TIMEZONE = "Europe/Chisinau"

# ── brand ─────────────────────────────────────────────────────────────────────
SUPPORT_LINK  = "https://t.me/SBF_Support"
NEWS_CHANNEL  = "https://t.me/SBFEconomics"
NEWS_CHANNEL_ID = "@SBFEconomics"
WEBSITE       = "https://sbfconsult.com"
BRAND_TAGLINE = "🎓 *SBF Academy* — ежедневный рыночный обзор"

# SPEC_tg_morning_brief_v2.md §3: кнопки утреннего пуша ведут на живой сайт
# (market_intel, lp.sbfconsult.com) -- отдельный домен от WEBSITE выше.
SITE_URL = "https://lp.sbfconsult.com"
