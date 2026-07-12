import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from . import models  # noqa: F401 - Mapper registrieren
from .routers import auth, calendar, pairs
from .services.sync_engine import scheduled_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
scheduler: Optional[AsyncIOScheduler] = None


async def _sync_job() -> None:
    try:
        await scheduled_sync(SessionLocal)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Sync-Job abgestuerzt: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    if settings.DEV_LOGIN:
        print(
            "[WARN] DEV_LOGIN=true - passwortloser Dev-Login aktiv. NUR lokal!",
            file=sys.stderr,
        )

    global scheduler
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")
    scheduler.add_job(
        _sync_job,
        IntervalTrigger(minutes=settings.SYNC_POLL_INTERVAL_MINUTES),
        id="calendar_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info(
        "Scheduler gestartet - Kalender-Sync alle %d min (Europe/Berlin)",
        settings.SYNC_POLL_INTERVAL_MINUTES,
    )
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Sync - Kalender-Sync", version="0.1.0", lifespan=lifespan)

# SessionMiddleware ZUERST, damit Authlib/Router darauf zugreifen koennen.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.APP_SECRET or "dev-insecure-secret",
    session_cookie="sync_session",
    same_site="lax",
    https_only=settings.COOKIE_SECURE,
    max_age=60 * 60 * 24 * 14,  # 14 Tage
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(pairs.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def app_config():
    """Nicht-sensible UI-Konfig (z.B. fuer die Anzeige des Sync-Intervalls)."""
    return {
        "poll_interval_minutes": settings.SYNC_POLL_INTERVAL_MINUTES,
        "backfill_days": settings.SYNC_BACKFILL_DAYS,
    }
