"""Thin httpx-Wrapper um die Google Calendar API.

Google bleibt Source of Truth - wir cachen nichts. Fehler werden in
`CalendarApiError` mit `status_code` gewrappt, damit Router/Engine sie auf
sprechende HTTP-Codes bzw. Sync-Logik mappen koennen.

Change-Detection: Inkrement-Sync ueber `syncToken` mit `singleEvents=true`
(instanzweise, inkl. Serien-Ausnahmen und `status=cancelled`).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
_TIMEOUT = 30.0


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


async def list_calendar_list(access_token: str) -> List[Dict[str, Any]]:
    """Alle Kalender aus der calendarList des verbundenen Accounts (fuer
    Auswahl-Dropdowns) - inkl. reingeteilter Fremd-Kalender."""
    items: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        while True:
            params: Dict[str, Any] = {"maxResults": 250, "showHidden": "true"}
            if page_token:
                params["pageToken"] = page_token
            resp = await client.get(
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

    `singleEvents=true`: liefert Einzel-Instanzen (Serien expandiert, Ausnahmen
    und Absagen als eigene Eintraege mit `status=cancelled`).
    """
    items: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    next_sync_token: Optional[str] = None
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
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
            resp = await client.get(
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
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events",
            headers={**_auth_headers(access_token), "Content-Type": "application/json"},
            params={"sendUpdates": send_updates},
            json=body,
        )
    if resp.status_code not in (200, 201):
        raise CalendarApiError(resp.status_code, resp.text)
    return resp.json()


async def patch_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    body: Dict[str, Any],
    send_updates: str = "none",
) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.patch(
            f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events/{event_id}",
            headers={**_auth_headers(access_token), "Content-Type": "application/json"},
            params={"sendUpdates": send_updates},
            json=body,
        )
    if resp.status_code != 200:
        raise CalendarApiError(resp.status_code, resp.text)
    return resp.json()


async def delete_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    send_updates: str = "none",
) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(
            f"{CALENDAR_API_BASE}/calendars/{_cal_path(calendar_id)}/events/{event_id}",
            headers=_auth_headers(access_token),
            params={"sendUpdates": send_updates},
        )
    # 204 = ok. 404/410 = schon weg, idempotent ok.
    if resp.status_code not in (200, 204, 404, 410):
        raise CalendarApiError(resp.status_code, resp.text)
