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

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..auth import google_calendar as gcal
from ..models import (
    CalendarSyncState,
    EventMapping,
    GoogleOAuthCredentials,
    SyncLock,
    SyncPair,
    SyncRun,
    User,
)
from . import google_calendar as svc
from . import mail

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


def _should_skip_event(ev: dict) -> bool:
    """Events, die keine Zeit blockieren, werden nicht gespiegelt:
    - `transparency=transparent` (als "frei" markiert),
    - vom verbundenen Account abgelehnt (`self` + responseStatus=declined).
    Ein bereits gespiegeltes solches Event wird wie eine Absage behandelt
    (Mirror wird entfernt)."""
    if ev.get("transparency") == "transparent":
        return True
    for att in ev.get("attendees") or []:
        if att.get("self") and att.get("responseStatus") == "declined":
            return True
    return False


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
        # "private" -> Eigentuemer sieht Details, andere mit Kalender-Zugriff nur
        # "Privat"/Belegt. "default" -> richtet sich nach Kalender-Freigabe.
        "visibility": "private" if pair.confidential else "default",
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
        base_title = ev.get("summary") or (pair.busy_title or "Belegt")
        if ev.get("description"):
            body["description"] = ev["description"]
        if ev.get("location"):
            body["location"] = ev["location"]
    else:
        # BUSY: generischer Titel, KEINE Details.
        base_title = pair.busy_title or "Belegt"
    # Frei waehlbares Herkunfts-Praefix, z.B. "(P) Meeting".
    prefix = (pair.title_prefix or "").strip()
    body["summary"] = f"{prefix} {base_title}".strip() if prefix else base_title
    # Optionale Farbe, damit Spiegel-Events im Ziel-Kalender auffallen.
    if pair.color_id:
        body["colorId"] = pair.color_id
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
    diese Quelle nutzen.

    WICHTIG (SQLite-Locking): waehrend der langsamen Google-Aufrufe darf KEINE
    Schreib-Transaktion offen gehalten werden - sonst laufen parallele Requests
    in "database is locked". Darum wird nach jedem Quell-Event committet (kurzes
    Lock-Fenster), nie ueber die Netzwerk-Calls hinweg.
    """
    state = get_state(db, user.id, source_cal)
    db.commit()  # evtl. neu angelegten State schreiben + Lock sofort freigeben
    items, new_token, was_full = await _fetch_changes(token, source_cal, state)

    counters: Dict[int, Counter] = {p.id: Counter() for p in pairs}
    for ev in items:
        # LOOP-SCHUTZ: eigene Kopien nie erneut spiegeln.
        if _is_mirror(ev):
            continue
        # Absage ODER "frei"/abgelehnt -> wie Absage behandeln (Mirror ggf. weg).
        cancelled = ev.get("status") == "cancelled" or _should_skip_event(ev)
        for p in pairs:
            await _apply(db, token, p, ev, cancelled, counters[p.id])
        db.commit()  # Schreibsperre nach jedem Quell-Event freigeben

    now = _utcnow()
    state = get_state(db, user.id, source_cal)
    state.sync_token = new_token
    if was_full:
        state.last_full_sync_at = now
    state.last_delta_at = now
    db.commit()
    return counters


def _write_run(
    db: Session,
    user: User,
    trigger: str,
    started: datetime,
    total: Counter,
    ok: bool,
    error: Optional[str],
) -> None:
    """Lauf-Log am ENDE schreiben (eine kurze Transaktion) - nicht am Anfang,
    sonst haelt die frueh angelegte Zeile die Schreibsperre ueber den ganzen
    Lauf offen."""
    db.add(
        SyncRun(
            user_id=user.id,
            trigger=trigger,
            started_at=started,
            finished_at=_utcnow(),
            created=total.created,
            updated=total.updated,
            deleted=total.deleted,
            ok=ok,
            error=error,
        )
    )
    db.commit()


async def sync_user(db: Session, user: User, trigger: str = "poll") -> Counter:
    """Ein vollstaendiger Sync-Durchlauf fuer einen User (alle aktiven Paare).

    Haelt die SQLite-Schreibsperre bewusst kurz (commit pro Quell-Event, Lauf-Log
    erst am Ende), damit parallele API-Requests nicht auf "database is locked"
    laufen.
    """
    started = _utcnow()
    total = Counter()

    try:
        token = await gcal.get_valid_access_token(db, user)
    except gcal.CalendarRevokedError:
        # Token widerrufen: die in get_valid_access_token geflushte Creds-Loeschung
        # MIT festschreiben (kein rollback) -> naechster Lauf skippt den User, keine
        # Wiederholung. Einmalig per Mail zum Neu-Verbinden auffordern.
        _write_run(db, user, trigger, started, total, ok=False, error="revoked")
        try:
            sent = await mail.send_reconnect_email(user)
            if sent:
                logger.info("Reconnect-Mail an %s gesendet (Token widerrufen)", user.email)
        except Exception:  # noqa: BLE001
            logger.exception("Reconnect-Mail fehlgeschlagen fuer user %s", user.id)
        return total
    except gcal.CalendarAuthError as exc:
        db.rollback()
        _write_run(
            db,
            user,
            trigger,
            started,
            total,
            ok=False,
            error="not_connected"
            if isinstance(exc, gcal.CalendarNotConnectedError)
            else str(exc)[:200],
        )
        return total

    pairs = db.query(SyncPair).filter_by(owner_user_id=user.id, active=True).all()
    by_source: Dict[str, List[SyncPair]] = defaultdict(list)
    for p in pairs:
        by_source[p.source_calendar_id].append(p)

    ok = True
    error_msg = ""
    for source_cal, group in by_source.items():
        group_ids = [p.id for p in group]
        try:
            counters = await _sync_source(db, token, user, source_cal, group)
            for p in group:
                p.last_run_at = _utcnow()
                p.last_status = "ok"
                p.last_error = None
                total.add(counters[p.id])
            db.commit()
        except Exception as exc:  # noqa: BLE001 - eine kaputte Quelle darf die
            # anderen nicht abbrechen (API-, Netzwerk- oder sonstiger Fehler).
            db.rollback()
            for pid in group_ids:
                p = db.get(SyncPair, pid)
                if p is not None:
                    p.last_run_at = _utcnow()
                    p.last_status = "error"
                    p.last_error = str(exc)[:500]
            db.commit()
            ok = False
            error_msg += f"[{source_cal}] {exc}; "
            logger.warning("Sync-Fehler fuer Quelle %s: %s", source_cal, exc)

    _write_run(db, user, trigger, started, total, ok=ok, error=error_msg or None)
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


# ---------- DB-gestuetzter Lauf-Lock (ein Sync pro User, ueber Prozesse hinweg) ----------
# Stale-Schwelle: laenger gehaltene Locks gelten als verwaist (Prozess-Crash) und
# duerfen uebernommen werden. Grosszuegig, damit ein langer Erst-Sync nicht
# faelschlich doppelt startet.
_LOCK_STALE = timedelta(minutes=30)


def _lock_is_stale(lock: SyncLock) -> bool:
    return (_utcnow() - lock.locked_at) > _LOCK_STALE


def is_sync_running(db: Session, user_id: int) -> bool:
    lock = db.get(SyncLock, user_id)
    return lock is not None and not _lock_is_stale(lock)


def acquire_sync_lock(db: Session, user_id: int, trigger: str) -> bool:
    """Atomar (SQLite serialisiert Writes): True, wenn dieser Prozess den Lock
    bekommt. Verwaiste Locks werden uebernommen."""
    now = _utcnow()
    lock = db.get(SyncLock, user_id)
    if lock is not None:
        if not _lock_is_stale(lock):
            return False
        lock.locked_at = now
        lock.trigger = trigger
        try:
            db.commit()
            return True
        except Exception:  # noqa: BLE001
            db.rollback()
            return False
    try:
        db.add(SyncLock(user_id=user_id, trigger=trigger, locked_at=now))
        db.commit()
        return True
    except IntegrityError:
        # Anderer Prozess war zwischen get und insert schneller.
        db.rollback()
        return False


def release_sync_lock(db: Session, user_id: int) -> None:
    lock = db.get(SyncLock, user_id)
    if lock is not None:
        db.delete(lock)
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()


async def run_sync_with_lock(db: Session, user: User, trigger: str) -> bool:
    """Erwirbt den DB-Lock und synct. False, wenn bereits ein Lauf aktiv ist.
    Der Lock wird am Ende immer freigegeben."""
    if not acquire_sync_lock(db, user.id, trigger):
        logger.info("Sync fuer user %s uebersprungen - laeuft bereits", user.id)
        return False
    try:
        await sync_user(db, user, trigger=trigger)
        return True
    finally:
        release_sync_lock(db, user.id)


async def scheduled_sync(session_factory) -> None:
    """Scheduler-Einstieg: synchronisiert jeden User mit hinterlegten Credentials.
    Ueber den DB-Lock harmlos, falls mehrere Worker gleichzeitig pollen."""
    db = session_factory()
    try:
        user_ids = [row[0] for row in db.query(GoogleOAuthCredentials.user_id).all()]
        for uid in user_ids:
            user = db.get(User, uid)
            if user is None:
                continue
            try:
                await run_sync_with_lock(db, user, trigger="poll")
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("scheduled sync fehlgeschlagen fuer user %s", uid)
    finally:
        db.close()


async def background_sync_user(user_id: int) -> None:
    """FastAPI-BackgroundTask nach der Response - eigene DB-Session, eigener
    Lock (no-op, falls parallel schon einer laeuft)."""
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is not None:
            await run_sync_with_lock(db, user, trigger="manual")
    except Exception:  # noqa: BLE001
        logger.exception("Hintergrund-Sync fehlgeschlagen fuer user %s", user_id)
    finally:
        db.close()
