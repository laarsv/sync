from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator


# ---------- Auth ----------


class MeOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    photo_url: Optional[str] = None
    role: str
    is_admin: bool


# ---------- Calendar connect ----------


class CalendarStatusOut(BaseModel):
    connected: bool
    google_email: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)


class AuthorizeUrlOut(BaseModel):
    auth_url: str


class CalendarCallbackIn(BaseModel):
    code: str
    redirect_uri: str
    state: str


class CalendarOut(BaseModel):
    id: str
    summary: str
    primary: bool = False
    access_role: Optional[str] = None
    background_color: Optional[str] = None


# ---------- Sync pairs ----------


class PairIn(BaseModel):
    source_calendar_id: str
    source_calendar_label: Optional[str] = None
    target_calendar_id: str
    target_calendar_label: Optional[str] = None
    detail_level: str = "busy"
    busy_title: str = "Belegt"
    title_prefix: str = Field(default="", max_length=32)
    confidential: bool = True
    active: bool = True

    @field_validator("detail_level")
    @classmethod
    def _valid_detail(cls, v: str) -> str:
        if v not in ("busy", "full"):
            raise ValueError("detail_level muss 'busy' oder 'full' sein")
        return v


class PairUpdate(BaseModel):
    source_calendar_id: Optional[str] = None
    source_calendar_label: Optional[str] = None
    target_calendar_id: Optional[str] = None
    target_calendar_label: Optional[str] = None
    detail_level: Optional[str] = None
    busy_title: Optional[str] = None
    title_prefix: Optional[str] = Field(default=None, max_length=32)
    confidential: Optional[bool] = None
    active: Optional[bool] = None

    @field_validator("detail_level")
    @classmethod
    def _valid_detail(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("busy", "full"):
            raise ValueError("detail_level muss 'busy' oder 'full' sein")
        return v


class PairOut(BaseModel):
    id: int
    source_calendar_id: str
    source_calendar_label: Optional[str] = None
    target_calendar_id: str
    target_calendar_label: Optional[str] = None
    detail_level: str
    busy_title: str
    title_prefix: str
    confidential: bool
    active: bool
    last_run_at: Optional[datetime] = None
    last_status: str
    last_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("last_run_at", "created_at")
    def _serialize_utc(self, dt: Optional[datetime]) -> Optional[str]:
        # Gespeichert wird naive UTC. Ohne explizite Kennung liest der Browser
        # den Zeitstempel als Lokalzeit -> 2h Versatz (CEST). Als UTC ausweisen.
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class SyncSummaryOut(BaseModel):
    created: int
    updated: int
    deleted: int


def _utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class SyncStartOut(BaseModel):
    # "started" = neuer Hintergrund-Sync gestartet; "running" = lief schon.
    status: str


class SyncRunOut(BaseModel):
    trigger: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    created: int
    updated: int
    deleted: int
    ok: bool
    error: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_serializer("started_at", "finished_at")
    def _ser_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return _utc_iso(dt)


class SyncStatusOut(BaseModel):
    running: bool
    last_run: Optional[SyncRunOut] = None
