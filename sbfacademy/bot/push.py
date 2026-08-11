"""JobQueue-задачи для брифинга."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram.error import BadRequest, Forbidden

from sbfacademy.briefing import ingest, render, store
from sbfacademy.core import db
from sbfacademy.core.config import BRAND_TAGLINE, DEFAULT_TIMEZONE

try:
    from sbfacademy.api.fcm import send_push_multicast as _fcm_multicast
    _FCM_ENABLED = True
except Exception:
    _FCM_ENABLED = False

log = logging.getLogger("sbfacademy.bot.push")

_FALLBACK = (
    "📈 <b>Мысль дня</b>\n\n"
    "«Диверсификация — единственный бесплатный обед в инвестировании.»\n"
    "— Гарри Марковиц\n\n"
    f"<i>{BRAND_TAGLINE}</i>"
)


async def ingest_job(context) -> None:
    """Генерирует брифинг из market_intel (реальный, детерминированный
    рыночный пайплайн — build_brief_v2.py/llm_context.py, см. tg_adapt.py).

    SPEC_tg_morning_brief_v2.md §0.5: раньше здесь сначала пробовался
    sbfacademy.briefing.generate (Telethon-чтение @SBFEconomics + отдельный
    вызов Claude) с фоллбэком на market_intel при неудаче. TG_API_HASH и
    ANTHROPIC_API_KEY в .env были пустыми -- generate.run() падал на первой
    же строке при КАЖДОМ вызове, без единого успешного прогона. Чинить эти
    credentials не стали: тот же Telethon-сессионный файл одновременно
    использует Vorovka2 (боевой процесс, не тестовый) -- второй клиент на
    том же .session -- реальный риск конфликта сессии, не гипотетический.
    Новая структурированная часть пуша (§2, tg_adapt.py) в любом случае
    берёт данные из market_intel, а не из @SBFEconomics-синтеза, так что
    generate.py стал не нужен архитектурно, не только из-за credentials.
    Файл сам по себе не удалён -- на случай если решение изменится."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if ingest.run(today):
        log.info("ingest_job: briefing from market_intel for %s", today)
    else:
        log.warning("ingest_job: no briefing for %s", today)


async def send_briefing(context) -> None:
    """Каждые 5 мин проверяет delivery_time юзеров и шлёт брифинг."""
    now_utc = datetime.now(timezone.utc)
    today   = now_utc.strftime("%Y-%m-%d")
    users   = db.get_all_active_users()
    sent = skipped = fallback_sent = 0

    for user in users:
        uid = user["user_id"]
        try:
            local_h, local_m = _local_hm(now_utc, user["timezone"] or DEFAULT_TIMEZONE)
            del_h,   del_m   = _parse_hm(user["delivery_time"] or "09:00")

            if (local_h, local_m) < (del_h, del_m):
                continue
            if db.already_delivered(uid, today):
                continue

            briefing = store.get_for_user(uid, today)
            if briefing is None:
                if local_h >= 23:
                    await context.bot.send_message(uid, _FALLBACK, parse_mode="HTML")
                    db.mark_delivered(uid, today)
                    db.log_action(uid, "briefing_fallback", today)
                    fallback_sent += 1
                else:
                    skipped += 1
                continue

            text, keyboard = render.render_push(briefing, user["timezone"] or DEFAULT_TIMEZONE)

            # SPEC_tg_morning_brief_v2.md §0.3: a permanent send failure (message
            # rejected by Telegram, e.g. over the 4096-char limit, or the user
            # blocked the bot) used to be swallowed by the outer except below
            # without calling mark_delivered -- already_delivered() stayed False,
            # so send_briefing retried the SAME failing send every 5 minutes
            # forever. Permanent failures now mark delivered (stop retrying);
            # transient ones (network etc.) don't, so they retry next tick.
            try:
                await context.bot.send_message(uid, text, parse_mode="HTML", reply_markup=keyboard)
            except (BadRequest, Forbidden) as e:
                log.error("send_briefing user=%d permanent failure: %s | len=%d text=%r",
                          uid, e, len(text), text[:500])
                db.mark_delivered(uid, today)
                db.log_action(uid, "briefing_send_failed", str(e)[:200])
                continue

            if _FCM_ENABLED:
                tokens = db.get_fcm_tokens(uid)
                if tokens:
                    _fcm_multicast(
                        tokens,
                        title="📊 " + briefing.headline[:60],
                        body=briefing.themes[0].body[:120] if briefing.themes else "Брифинг готов",
                        data={"type": "briefing", "date": today},
                    )

            db.mark_delivered(uid, today)
            db.log_action(uid, "briefing_sent", today)
            sent += 1

        except Exception as e:
            log.error("send_briefing user=%d: %s", uid, e)

    if sent or fallback_sent:
        log.info("send_briefing: sent=%d fallback=%d skipped=%d", sent, fallback_sent, skipped)


def _parse_hm(t: str) -> tuple[int, int]:
    try:
        h, m = t.split(":")
        return int(h), int(m)
    except Exception:
        return 9, 0


# SPEC_tg_morning_brief_v2.md §0.4/§5: a fixed UTC-offset table has no DST --
# e.g. Europe/Moscow doesn't observe DST but Europe/London/Chisinau do, so a
# static table silently drifts by an hour part of the year. zoneinfo handles
# this correctly and needs no manual offset list at all.
def _local_hm(now_utc: datetime, tz_name: str) -> tuple[int, int]:
    try:
        local = now_utc.astimezone(ZoneInfo(tz_name))
    except Exception:
        local = now_utc.astimezone(ZoneInfo(DEFAULT_TIMEZONE))
    return local.hour, local.minute
