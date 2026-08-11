"""FastAPI-приложение SBFAcademy.

Запуск:
    uvicorn sbfacademy.api.main:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import logging
from pathlib import Path

# Загружаем .env до всех остальных импортов (BOT_TOKEN нужен для initData)
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_ENV_FILE))
    except ImportError:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sbfacademy.api.routes.auth import router as auth_router, me_router
from sbfacademy.api.routes.briefing import router as briefing_router
from sbfacademy.api.routes.calendar import router as calendar_router
from sbfacademy.api.routes.cheatsheets import router as cheatsheets_router
from sbfacademy.api.routes.checklist import router as checklist_router
from sbfacademy.api.routes.devices import router as devices_router
from sbfacademy.api.routes.journal import router as journal_router
from sbfacademy.api.routes.markets import router as markets_router
from sbfacademy.api.routes.profile import router as profile_router
from sbfacademy.api.routes.watchlist import router as watchlist_router
from sbfacademy.core import db

log = logging.getLogger("sbfacademy.api")

app = FastAPI(
    title="SBFAcademy API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS — Telegram Mini App открывается в iframe; APK использует null origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# index.html/app.js/styles.css не отдавали никакого Cache-Control вообще —
# в отличие от market_intel (там explicit no-cache), из-за чего мобильные
# WebView (Telegram Mini App) применяли собственную эвристику и держали
# старый index.html куда дольше, чем нужно, независимо от версии в query
# string у самих скриптов. HTML — всегда revalidate; versioned-ассеты
# (?v=N меняется при правке) можно кэшировать долго без риска отдать stale.
@app.middleware("http")
async def _cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache"
    elif "v=" in request.url.query and (path.endswith(".js") or path.endswith(".css")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


# ── роутеры ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(briefing_router)
app.include_router(calendar_router)
app.include_router(cheatsheets_router)
app.include_router(checklist_router)
app.include_router(devices_router)
app.include_router(journal_router)
app.include_router(markets_router)
app.include_router(profile_router)
app.include_router(watchlist_router)


# ── app version endpoint ───────────────────────────────────────────────────────
@app.get("/api/version")
async def version():
    return {"version": "1.0.0", "build": "2026-06-28"}


# ── TMA auth (exchange initData → JWT) ───────────────────────────────────────
class TmaAuthBody(BaseModel):
    init_data: str


@app.post("/api/auth/tma")
async def auth_tma(body: TmaAuthBody):
    from sbfacademy.api.auth import validate_init_data
    from sbfacademy.api.jwt_utils import create_access_token

    data = validate_init_data(body.init_data)
    if not data or "user" not in data:
        raise HTTPException(401, "Invalid initData")

    tg_user = data["user"]
    tg_id   = int(tg_user["id"])
    user_id = db.resolve_telegram_user(
        tg_id,
        username=tg_user.get("username"),
        full_name=f"{tg_user.get('first_name', '')} {tg_user.get('last_name', '')}".strip(),
    )
    access_token = create_access_token(user_id)
    return {"access_token": access_token, "token_type": "bearer"}


# ── health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"ok": True}


# ── startup ───────────────────────────────────────────────────────────────────
@app.get("/api/mindset")
async def mindset():
    import json, random
    from pathlib import Path
    _f = Path(__file__).parent.parent / "data" / "mindset_prompts.json"
    prompts = json.loads(_f.read_text("utf-8")) if _f.exists() else []
    today = __import__("datetime").date.today().toordinal()
    prompt = prompts[today % len(prompts)] if prompts else ""
    return {"prompt": prompt}


@app.on_event("startup")
async def on_startup():
    db.init_db()
    try:
        from sbfacademy.data.seed import seed_all
        seed_all()
    except Exception as e:
        log.warning("seed failed: %s", e)
    log.info("DB initialized")


# ── static files (webapp/) — монтируем последним чтобы не перекрывать API ────
_WEBAPP_DIR = Path(__file__).parent.parent.parent / "webapp"
if _WEBAPP_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_WEBAPP_DIR), html=True), name="webapp")
