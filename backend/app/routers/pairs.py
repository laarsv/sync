import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import google_calendar as gcal
from ..deps import get_current_user, get_db
from ..models import SyncPair, SyncRun, User
from ..schemas import (
    PairIn,
    PairOut,
    PairUpdate,
    SyncRunOut,
    SyncStartOut,
    SyncStatusOut,
)
from ..services import sync_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pairs", tags=["pairs"])


def _get_owned_pair(db: Session, user: User, pair_id: int) -> SyncPair:
    pair = db.get(SyncPair, pair_id)
    if pair is None or pair.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pair_not_found")
    return pair


async def _try_token(db: Session, user: User) -> Optional[str]:
    """Access-Token holen, aber ohne Hard-Fail (fuer Best-effort-Reconcile).
    Faengt bewusst breit (auch Netzwerkfehler) - der Aufrufer soll dadurch nie
    500en."""
    try:
        return await gcal.get_valid_access_token(db, user)
    except Exception:  # noqa: BLE001
        logger.info("Token-Abruf fuer Best-effort-Reconcile fehlgeschlagen", exc_info=True)
        return None


@router.get("", response_model=List[PairOut])
def list_pairs(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> List[PairOut]:
    pairs = (
        db.query(SyncPair)
        .filter_by(owner_user_id=current_user.id)
        .order_by(SyncPair.id.asc())
        .all()
    )
    return [PairOut.model_validate(p) for p in pairs]


@router.post("", response_model=PairOut, status_code=status.HTTP_201_CREATED)
def create_pair(
    payload: PairIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PairOut:
    if payload.source_calendar_id == payload.target_calendar_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quelle und Ziel duerfen nicht identisch sein.",
        )
    pair = SyncPair(
        owner_user_id=current_user.id,
        source_calendar_id=payload.source_calendar_id,
        source_calendar_label=payload.source_calendar_label,
        target_calendar_id=payload.target_calendar_id,
        target_calendar_label=payload.target_calendar_label,
        detail_level=payload.detail_level,
        busy_title=payload.busy_title or "Belegt",
        title_prefix=(payload.title_prefix or "").strip(),
        confidential=payload.confidential,
        active=payload.active,
    )
    db.add(pair)
    db.flush()
    if pair.active:
        # Bestehende Quell-Events sollen sofort (beim naechsten Sync) gespiegelt
        # werden -> Full-Sync der Quelle erzwingen.
        sync_engine.reset_source_state(db, current_user.id, pair.source_calendar_id)
    db.commit()
    return PairOut.model_validate(pair)


@router.patch("/{pair_id}", response_model=PairOut)
async def update_pair(
    pair_id: int,
    payload: PairUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PairOut:
    pair = _get_owned_pair(db, current_user, pair_id)
    old = {
        "source": pair.source_calendar_id,
        "target": pair.target_calendar_id,
        "detail_level": pair.detail_level,
        "busy_title": pair.busy_title,
        "title_prefix": pair.title_prefix,
        "confidential": pair.confidential,
        "active": pair.active,
    }

    data = payload.model_dump(exclude_unset=True)
    if data.get("title_prefix") is not None:
        data["title_prefix"] = data["title_prefix"].strip()
    new_source = data.get("source_calendar_id", pair.source_calendar_id)
    new_target = data.get("target_calendar_id", pair.target_calendar_id)
    if new_source == new_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quelle und Ziel duerfen nicht identisch sein.",
        )

    for k, v in data.items():
        setattr(pair, k, v)
    if not pair.busy_title:
        pair.busy_title = "Belegt"
    db.flush()

    moved = pair.source_calendar_id != old["source"] or pair.target_calendar_id != old["target"]
    detail_changed = pair.detail_level != old["detail_level"]
    content_changed = (
        pair.busy_title != old["busy_title"]
        or pair.title_prefix != old["title_prefix"]
        or pair.confidential != old["confidential"]
    )
    deactivating = old["active"] and not pair.active
    activating = not old["active"] and pair.active

    # Re-Sync erzwingen (reine DB-Aenderung), damit Aenderungen beim naechsten
    # Lauf greifen - inkl. reiner Titel-/Praefix-/Sichtbarkeits-Aenderungen, die
    # bestehende Mirrors nur re-patchen.
    if pair.active and (moved or detail_changed or content_changed or activating):
        sync_engine.reset_source_state(db, current_user.id, pair.source_calendar_id)
        if old["source"] != pair.source_calendar_id:
            sync_engine.reset_source_state(db, current_user.id, old["source"])

    # Den Edit ZUERST festschreiben - unabhaengig von der Google-Reconcile.
    db.commit()
    result = PairOut.model_validate(pair)

    # Google-Reconcile ist best-effort: alte Mirrors auf dem ALTEN Ziel loeschen,
    # wenn Quelle/Ziel/Detailstufe wechselt oder deaktiviert wird (sonst blieben
    # alte Details als Rest haengen). Schlaegt das fehl (Google-API-Fehler o.ae.),
    # bleibt der Edit trotzdem gespeichert und der naechste Sync raeumt auf -
    # kein 500.
    if moved or detail_changed or deactivating:
        try:
            token = await _try_token(db, current_user)
            if token is not None:
                await sync_engine.cleanup_pair(
                    db, token, pair, target_calendar_id=old["target"]
                )
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.warning(
                "Reconcile nach Paar-Update fehlgeschlagen (best-effort)",
                exc_info=True,
            )

    return result


@router.delete("/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pair(
    pair_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pair = _get_owned_pair(db, current_user, pair_id)
    # Best-effort: gespiegelte Ziel-Events entfernen, bevor das Paar (und via
    # Cascade seine Mappings) geloescht wird. Fehler hier duerfen das Loeschen
    # nicht verhindern.
    try:
        token = await _try_token(db, current_user)
        if token is not None:
            await sync_engine.cleanup_pair(db, token, pair)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("Cleanup beim Loeschen fehlgeschlagen (best-effort)", exc_info=True)
    db.delete(pair)
    db.commit()
    return None


@router.post(
    "/sync-now", response_model=SyncStartOut, status_code=status.HTTP_202_ACCEPTED
)
async def sync_now(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncStartOut:
    """Startet den Sync als Hintergrund-Task und kehrt sofort zurueck. Den
    Fortschritt/das Ergebnis holt das Frontend ueber GET /sync-status."""
    if not gcal.is_connected(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="calendar_not_connected"
        )
    # Advisory-Check: verhindert unnoetiges Spawnen. Die eigentliche Absicherung
    # (ein Lauf pro User, auch ueber mehrere Worker) ist der DB-Lock im Task.
    if sync_engine.is_sync_running(db, current_user.id):
        return SyncStartOut(status="running")
    background.add_task(sync_engine.background_sync_user, current_user.id)
    return SyncStartOut(status="started")


@router.get("/sync-status", response_model=SyncStatusOut)
def sync_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> SyncStatusOut:
    last = (
        db.query(SyncRun)
        .filter_by(user_id=current_user.id)
        .order_by(SyncRun.id.desc())
        .first()
    )
    return SyncStatusOut(
        running=sync_engine.is_sync_running(db, current_user.id),
        last_run=SyncRunOut.model_validate(last) if last else None,
    )
