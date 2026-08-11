"""Firebase Cloud Messaging — отправка push-уведомлений на Android."""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Optional

log = logging.getLogger("sbfacademy.fcm")

_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")


@lru_cache(maxsize=1)
def _get_app():
    """Инициализирует firebase_admin один раз."""
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return firebase_admin.get_app()

    if _SERVICE_ACCOUNT_JSON:
        cred = credentials.Certificate(json.loads(_SERVICE_ACCOUNT_JSON))
    elif _SERVICE_ACCOUNT_PATH:
        cred = credentials.Certificate(_SERVICE_ACCOUNT_PATH)
    else:
        raise RuntimeError(
            "Укажи FIREBASE_SERVICE_ACCOUNT_JSON или FIREBASE_SERVICE_ACCOUNT_PATH в .env"
        )
    return firebase_admin.initialize_app(cred)


def send_push(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """Отправляет одно push-уведомление. Возвращает True при успехе."""
    try:
        _get_app()
        from firebase_admin import messaging

        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(priority="high"),
            token=fcm_token,
        )
        messaging.send(msg)
        return True
    except Exception as e:
        log.warning("FCM send failed token=%s…: %s", fcm_token[:12], e)
        return False


def send_push_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> tuple[int, int]:
    """Рассылает push нескольким токенам. Возвращает (success_count, failure_count)."""
    if not tokens:
        return 0, 0
    try:
        _get_app()
        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(priority="high"),
            tokens=tokens,
        )
        resp = messaging.send_each_for_multicast(message)
        return resp.success_count, resp.failure_count
    except Exception as e:
        log.error("FCM multicast failed: %s", e)
        return 0, len(tokens)
