"""Sync-Engine: spiegelt Quell-Events in Ziel-Kalender.

Adressiert die Landminen:
  * LOOP-SCHUTZ      - jedes gespiegelte Event traegt `extendedProperties.private.
                       syncSource`. Beim Lesen einer Quelle werden markierte
                       Events ignoriert -> eine Kopie wird nie erneut gespiegelt.
                       Kritisch, weil ein Kalender gleichzeitig Quelle UND Ziel
                       sein kann.
  * IDEMPOTENZ       - `event_mappings` (UNIQUE pair+source_event_id). Updates
                       treffen dasselbe Ziel-Event, kein Duplikat.
  * DELETE-PROPAGATION - `status=cancelled`/geloescht (aus syncToken-Deltas) ->
                       gespiegelter Block wird geloescht.
  * SERIENTERMINE    - `singleEvents=true`: Instanzen einzeln, Ausnahmen/Absagen
                       als eigene Eintraege. Gematcht ueber die (stabile)
                       Instanz-ID.
  * BUSY-MODUS       - generischer Titel, keine Details, keine Teilnehmer.
  * KEINE INVITES    - jeder Schreib-/Loeschvorgang mit sendUpdates=none.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..config import settings
from ..auth import google_calendar as gcal
from ..models import (
    CalendarSyncState,
    EventMapping,
    GoogleOAuthCredentials,
    SyncPair,
    SyncRun,
    User,
)
from . import google_calendar as svc

logger = logging.getLogger(__name__)

# Herkunfts-Markierung in extendedProperties.private.
MIRROR_MARKER_KEY = "syncSource"
MIRROR_MARKER_VALUE = "kw-sync"
SEND_UPDATES = "none"  # NIE Einladungen/Absagen an echte Teilnehmer verschicken.


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _rfc3339(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Counter:
    created: int = 0
    updated: int = 0
    deleted: int = 0

    def add(self, other: "Counter") -> None:
        self.created += other.created
        self.updated += other.updated
        self.deleted += other.deleted


# ---------- Helpers ----------


def _is_mirror(ev: dict) -> bool:
    priv = (ev.get("extendedProperties") or {}).get("private") or {}
    return priv.get(MIRROR_MARKER_KEY) == MIRROR_MARKER_VALUE


def _copy_time(t: Optional[dict]) -> dict:
    if not t:
        return {}
    if t.get("date"):
        return {"date": t["date"]}
    out: Dict[str, str] = {}
    if t.get("dateTime"):
        out["dateTime"] = t["dateTime"]
    if t.get("timeZone"):
        out["timeZone"] = t["timeZone"]
    return out


def _build_body(pair: SyncPair, ev: dict) -> dict:
    body: dict = {
        "start": _copy_time(ev.get("start")),
        "end": _copy_time(ev.get("end")),
        "transparency": "opaque",
        "visibility": "private",
        # Keine Erinnerungen auf dem Spiegel-Event.
        "reminders": {"useDefault": False, "overrides": []},
        "extendedProperties": {
            "private": {
                MIRROR_MARKER_KEY: MIRROR_MARKER_VALUE,
                "syncPair": str(pair.id),
                "syncSrcCal": pair.source_calendar_id,
                "syncSrcEvt": ev.get("id", ""),
            }
        },
    }
    if pair.detail_level == "full":
        body["summary"] = ev.get("summary") or (pair.busy_title or "Belegt")
        if ev.get("description"):
            body["description"] = ev["description"]
        if ev.get("location"):
            body["location"] = ev["location"]
    else:
        # BUSY: generischer Titel, KEINE Details.
        body["summary"] = pair.busy_title or "Belegt"
    # NIE Teilnehmer spiegeln - ein Mirror traegt keine Gaesteliste.
    return body


def get_state(db: Session, user_id: int, calendar_id: str) -> CalendarSyncState:
    st = (
        db.query(CalendarSyncState)
        .filter_by(user_id=user_id, calendar_id=calendar_id)
        .one_or_none()
    )
    if st is None:
        st = CalendarSyncState(user_id=user_id, calendar_id=calendar_id)
        db.add(st)
        db.flush()
    return st


def reset_source_state(db: Session, user_id: int, calendar_id: str) -> None:
    """Erzwingt beim naechsten Lauf einen Full-Sync (z.B. nach Anlegen/Aktivieren
    eines Paares), damit bestehende Quell-Events sofort gespiegelt werden."""
    st = get_state(db, user_id, calendar_id)
    st.sync_token = None
    db.flush()


def _needs_full(state: CalendarSyncState) -> bool:
    if not state.sync_token:
        return True
    if state.last_full_sync_at is None:
        return True
    if _utcnow() - state.last_full_sync_at > timedelta(
        hours=settings.SYNC_FULL_RESYNC_HOURS
    ):
        return True
    return False


async def _fetch_changes(
    token: str, calendar_id: str, state: CalendarSyncState
) -> Tuple[List[dict], Optional[str], bool]:
    if _needs_full(state):
        time_min = _rfc3339(_utcnow() - timedelta(days=settings.SYNC_BACKFILL_DAYS))
        items, tok = await svc.list_events_sync(token, calendar_id, time_min_iso=time_min)
        return items, tok, True
    try:
        items, tok = await svc.list_events_sync(
            token, calendar_id, sync_token=state.sync_token
        )
        return items, tok, False
    except svc.CalendarApiError as exc:
        if exc.status_code == 410:
            # syncToken abgelaufen -> Full-Sync.
            time_min = _rfc3339(_utcnow() - timedelta(days=settings.SYNC_BACKFILL_DAYS))
            items, tok = await svc.list_events_sync(
                token, calendar_id, time_min_iso=time_min
            )
            return items, tok, True
        raise


def _get_mapping(db: Session, pair_id: int, source_event_id: str) -> Optional[EventMapping]:
    return (
        db.query(EventMapping)
        .filter_by(sync_pair_id=pair_id, source_event_id=source_event_id)
        .one_or_none()
    )


async def _apply(
    db: Session, token: str, pair: SyncPair, ev: dict, cancelled: bool, counter: Counter
) -> None:
    ev_id = ev.get("id")
    if not ev_id:
        return
    mapping = _get_mapping(db, pair.id, ev_id)
    now = _utcnow()

    # ---- DELETE-PROPAGATION ----
    if cancelled:
        if mapping and mapping.status == "active" and mapping.target_event_id:
            try:
                await svc.delete_event(
                    token, pair.target_calendar_id, mapping.target_event_id, SEND_UPDATES
                )
            except svc.CalendarApiError as exc:
                if exc.status_code not in (404, 410):
                    raise
            mapping.status = "deleted"
            mapping.last_synced_at = now
            counter.deleted += 1
        return

    body = _build_body(pair, ev)

    # ---- UPDATE (Idempotenz: dasselbe Ziel-Event patchen) ----
    if mapping and mapping.status == "active" and mapping.target_event_id:
        try:
            await svc.patch_event(
                token, pair.target_calendar_id, mapping.target_event_id, body, SEND_UPDATES
            )
            counter.updated += 1
        except svc.CalendarApiError as exc:
            if exc.status_code in (404, 410):
                # Ziel-Event extern geloescht -> neu anlegen.
                created = await svc.insert_event(
                    token, pair.target_calendar_id, body, SEND_UPDATES
                )
                mapping.target_event_id = created.get("id")
                counter.created += 1
            else:
                raise
        mapping.source_updated = ev.get("updated")
        mapping.source_ical_uid = ev.get("iCalUID")
        mapping.source_recurring_event_id = ev.get("recurringEventId")
        mapping.last_synced_at = now
        return

    # ---- CREATE ----
    created = await svc.insert_event(token, pair.target_calendar_id, body, SEND_UPDATES)
    if mapping:
        mapping.target_event_id = created.get("id")
        mapping.status = "active"
        mapping.source_updated = ev.get("updated")
        mapping.source_ical_uid = ev.get("iCalUID")
        mapping.source_recurring_event_id = ev.get("recurringEventId")
        mapping.last_synced_at = now
    else:
        db.add(
            EventMapping(
                sync_pair_id=pair.id,
                source_event_id=ev_id,
                source_ical_uid=ev.get("iCalUID"),
                source_recurring_event_id=ev.get("recurringEventId"),
                target_event_id=created.get("id"),
                source_updated=ev.get("updated"),
                status="active",
                last_synced_at=now,
            )
        )
    counter.created += 1


async def _sync_source(
    db: Session, token: str, user: User, source_cal: str, pairs: List[SyncPair]
) -> Dict[int, Counter]:
    """Liest die Quelle EINMAL und verteilt die Aenderungen an alle Paare, die
    diese Quelle nutzen."""
    state = get_state(db, user.id, source_cal)
    items, new_token, was_full = await _fetch_changes(token, source_cal, state)

    counters: Dict[int, Counter] = {p.id: Counter() for p in pairs}
    for ev in items:
        # LOOP-SCHUTZ: eigene Kopien nie erneut spiegeln.
        if _is_mirror(ev):
            continue
        cancelled = ev.get("status") == "cancelled"
        for p in pairs:
            await _apply(db, token, p, ev, cancelled, counters[p.id])

    now = _utcnow()
    state.sync_token = new_token
    if was_full:
        state.last_full_sync_at = now
    state.last_delta_at = now
    db.flush()
    return counters


async def sync_user(db: Session, user: User, trigger: str = "poll") -> Counter:
    """Ein vollstaendiger Sync-Durchlauf fuer einen User (alle aktiven Paare)."""
    run = SyncRun(user_id=user.id, trigger=trigger, started_at=_utcnow())
    db.add(run)
    db.flush()
    total = Counter()

    try:
        token = await gcal.get_valid_access_token(db, user)
    except gcal.CalendarNotConnectedError:
        run.ok = False
        run.error = "not_connected"
        run.finished_at = _utcnow()
        db.flush()
        return total

    pairs = (
        db.query(SyncPair).filter_by(owner_user_id=user.id, active=True).all()
    )
    by_source: Dict[str, List[SyncPair]] = defaultdict(list)
    for p in pairs:
        by_source[p.source_calendar_id].append(p)

    for source_cal, group in by_source.items():
        try:
            counters = await _sync_source(db, token, user, source_cal, group)
            for p in group:
                c = counters[p.id]
                p.last_run_at = _utcnow()
                p.last_status = "ok"
                p.last_error = None
                total.add(c)
        except (svc.CalendarApiError, gcal.CalendarAuthError) as exc:
            for p in group:
                p.last_run_at = _utcnow()
                p.last_status = "error"
                p.last_error = str(exc)[:500]
            run.ok = False
            run.error = (run.error or "") + f"[{source_cal}] {exc}; "
            logger.warning("Sync-Fehler fuer Quelle %s: %s", source_cal, exc)
        db.flush()

    run.finished_at = _utcnow()
    run.created = total.created
    run.updated = total.updated
    run.deleted = total.deleted
    db.flush()
    return total


async def cleanup_pair(
    db: Session,
    token: str,
    pair: SyncPair,
    target_calendar_id: Optional[str] = None,
) -> int:
    """Loescht alle gespiegelten Ziel-Events eines Paares (bei Delete/Deaktivieren
    oder Ziel-Wechsel). `target_calendar_id` erlaubt Loeschen auf dem ALTEN Ziel."""
    target = target_calendar_id or pair.target_calendar_id
    n = 0
    maps = (
        db.query(EventMapping)
        .filter_by(sync_pair_id=pair.id, status="active")
        .all()
    )
    for m in maps:
        if m.target_event_id:
            try:
                await svc.delete_event(token, target, m.target_event_id, SEND_UPDATES)
            except svc.CalendarApiError as exc:
                if exc.status_code not in (404, 410):
                    raise
        m.status = "deleted"
        m.last_synced_at = _utcnow()
        n += 1
    db.flush()
    return n


async def scheduled_sync(session_factory) -> None:
    """Scheduler-Einstieg: synchronisiert jeden User mit hinterlegten Credentials."""
    db = session_factory()
    try:
        user_ids = [row[0] for row in db.query(GoogleOAuthCredentials.user_id).all()]
        for uid in user_ids:
            user = db.get(User, uid)
            if user is None:
                continue
            try:
                await sync_user(db, user, trigger="poll")
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("scheduled sync_user fehlgeschlagen fuer user %s", uid)
    finally:
        db.close()
