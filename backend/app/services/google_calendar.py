"""Thin httpx-Wrapper um die Google Calendar API.

Google bleibt Source of Truth - wir cachen nichts. Fehler werden in
`CalendarApiError` mit `status_code` gewrappt, damit Router/Engine sie auf
sprechende HTTP-Codes bzw. Sync-Logik mappen koennen.

Change-Detection: Inkrement-Sync ueber `syncToken` mit `singleEvents=true`
(instanzweise, inkl. Serien-Ausnahmen und `status=cancelled`).

Rate-Limits: Google antwortet bei zu vielen Requests mit 403 (reason
`rateLimitExceeded`/`userRateLimitExceeded`) oder 429. Solche - plus transiente
5xx - werden mit exponentiellem Backoff (+ Jitter, `Retry-After` beachtet)
wiederholt. Echte 403 (fehlende Rechte) NICHT.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
_TIMEOUT = 30.0

# Retry-Konfiguration.
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0
_BACKOFF_CAP = 32.0


class CalendarApiError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _auth_headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _cal_path(calendar_id: str) -> str:
    # Kalender-IDs enthalten '@' etc. -> encodieren.
    return quote(calendar_id, safe="")


async def _pace_write() -> None:
    """Kleine Pause nach jedem Schreibvorgang, um Rate-Limits zu glaetten."""
    ms = settings.SYNC_WRITE_PAUSE_MS
    if ms > 0:
        await asyncio.sleep(ms / 1000.0)


def _is_rate_limited(resp: httpx.Response) -> bool:
    if resp.status_code == 429:
        return True
    if resp.status_code == 403:
        try:
            reason = resp.json()["error"]["errors"][0]["reason"]
        except Exception:  # noqa: BLE001 - unparsbarer 403 -> nicht retryen
            return False
        return reason in ("rateLimitExceeded", "userRateLimitExceeded")
    return False


async def _request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
) -> httpx.Response:
    """httpx-Request mit Backoff-Retry bei Rate-Limit/transienten Fehlern."""
    delay = _BACKOFF_BASE
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for attempt in range(_MAX_RETRIES + 1):
            resp = await client.request(
                method, url, headers=headers, params=params, json=json
            )
            retriable = resp.status_code in _RETRY_STATUSES or _is_rate_limited(resp)
            if not retriable or attempt == _MAX_RETRIES:
                return resp
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = float(retry_after)
            else:
                wait = delay + random.uniform(0, delay)  # Full-Jitter
                delay = min(delay * 2, _BACKOFF_CAP)
            logger.warning(
                "Google %s -> %s (rate/transient), Retry in %.1fs (Versuch %d/%d)",
                method,
                resp.status_code,
                wait,
                attempt + 1,
                _MAX_RETRIES,
            )
            await asyncio.sleep(wait)
    return resp  # pragma: no cover - Schleife returned immer vorher


async def list_calendar_list(access_token: str) -> List[Dict[str, Any]]:
    """Alle Kalender aus der calendarList des verbundenen Accounts (fuer
    Auswahl-Dropdowns) - inkl. reingeteilter Fremd-Kalender."""
    items: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    while True:
        params: Dict[str, Any] = {"maxResults": 250, "showHidden": "true"}
        if page_token:
            params["pageToken"] = page_token
        resp = await _request(
            "GET",
            f"{CALENDAR_API_BASE}/users/me/calendarList",
            headers=_auth_headers(access_token),
            params=params,
        )
        if resp.status_code != 200:
            raise CalendarApiError(resp.status_code, resp.text)
        data = resp.json()
        items.extend(data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


async def list_events_sync(
    access_token: str,
    calendar_id: str,
    sync_token: Optional[str] = None,
    time_min_iso: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Full-Sync (ohne sync_token, mit timeMin) oder Inkrement (mit sync_token).

    Gibt `(items, next_sync_token)` zurueck. `next_sync_token` steht nur auf der
    letzten Seite. Bei ungueltigem syncToken liefert Google 410 - der Caller
    macht dann einen Full-Sync.
    """
    items: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    next_sync_token: Optional[str] = None
    while True:
        params: Dict[str, Any] = {"singleEvents": "true", "maxResults": 250}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            params["showDeleted"] = "true"
            if time_min_iso:
                params["timeMin"] = time_min_iso
        if page_token:
            params["pageToken"] = page_token
        resp = await _request(
            "GET",
            f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events",
            headers=_auth_headers(access_token),
            params=params,
        )
        if resp.status_code != 200:
            raise CalendarApiError(resp.status_code, resp.text)
        data = resp.json()
        items.extend(data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            next_sync_token = data.get("nextSyncToken")
            break
    return items, next_sync_token


async def insert_event(
    access_token: str,
    calendar_id: str,
    body: Dict[str, Any],
    send_updates: str = "none",
) -> Dict[str, Any]:
    resp = await _request(
        "POST",
        f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events",
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        params={"sendUpdates": send_updates},
        json=body,
    )
    if resp.status_code not in (200, 201):
        raise CalendarApiError(resp.status_code, resp.text)
    result = resp.json()
    await _pace_write()
    return result


async def patch_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    body: Dict[str, Any],
    send_updates: str = "none",
) -> Dict[str, Any]:
    resp = await _request(
        "PATCH",
        f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events/{event_id}",
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        params={"sendUpdates": send_updates},
        json=body,
    )
    if resp.status_code != 200:
        raise CalendarApiError(resp.status_code, resp.text)
    result = resp.json()
    await _pace_write()
    return result


async def delete_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    send_updates: str = "none",
) -> None:
    resp = await _request(
        "DELETE",
        f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events/{event_id}",
        headers=_auth_headers(access_token),
        params={"sendUpdates": send_updates},
    )
    # 204 = ok. 404/410 = schon weg, idempotent ok.
    if resp.status_code not in (200, 204, 404, 410):
        raise CalendarApiError(resp.status_code, resp.text)
    await _pace_write()
