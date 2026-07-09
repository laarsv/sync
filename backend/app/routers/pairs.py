from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import google_calendar as gcal
from ..deps import get_current_user, get_db
from ..models import SyncPair, User
from ..schemas import PairIn, PairOut, PairUpdate, SyncSummaryOut
from ..services import sync_engine

router = APIRouter(prefix="/api/pairs", tags=["pairs"])


def _get_owned_pair(db: Session, user: User, pair_id: int) -> SyncPair:
    pair = db.get(SyncPair, pair_id)
    if pair is None or pair.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pair_not_found")
    return pair


async def _try_token(db: Session, user: User) -> Optional[str]:
    """Access-Token holen, aber ohne Hard-Fail (fuer Best-effort-Cleanup)."""
    try:
        return await gcal.get_valid_access_token(db, user)
    except gcal.CalendarAuthError:
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
    old_target = pair.target_calendar_id
    old_source = pair.source_calendar_id

    data = payload.model_dump(exclude_unset=True)
    new_source = data.get("source_calendar_id", pair.source_calendar_id)
    new_target = data.get("target_calendar_id", pair.target_calendar_id)
    if new_source == new_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quelle und Ziel duerfen nicht identisch sein.",
        )

    structural = any(
        k in data for k in ("source_calendar_id", "target_calendar_id", "detail_level")
    )
    deactivating = data.get("active") is False and pair.active
    activating = data.get("active") is True and not pair.active

    for k, v in data.items():
        setattr(pair, k, v)
    if pair.busy_title == "":
        pair.busy_title = "Belegt"
    db.flush()

    # Reconcile bestehende Spiegel-Events, wenn sich Struktur aendert oder das
    # Paar deaktiviert wird. Cleanup laeuft auf dem ALTEN Ziel.
    if structural or deactivating:
        token = await _try_token(db, current_user)
        if token is not None:
            await sync_engine.cleanup_pair(
                db, token, pair, target_calendar_id=old_target
            )

    # Bei aktivem Paar + Strukturaenderung/Reaktivierung Full-Sync erzwingen,
    # damit neu/erneut gespiegelt wird.
    if pair.active and (structural or activating):
        sync_engine.reset_source_state(db, current_user.id, pair.source_calendar_id)
        if old_source != pair.source_calendar_id:
            sync_engine.reset_source_state(db, current_user.id, old_source)

    db.commit()
    return PairOut.model_validate(pair)


@router.delete("/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pair(
    pair_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pair = _get_owned_pair(db, current_user, pair_id)
    token = await _try_token(db, current_user)
    if token is not None:
        await sync_engine.cleanup_pair(db, token, pair)
    db.delete(pair)
    db.commit()
    return None


@router.post("/sync-now", response_model=SyncSummaryOut)
async def sync_now(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> SyncSummaryOut:
    try:
        counter = await sync_engine.sync_user(db, current_user, trigger="manual")
    except gcal.CalendarNotConnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="calendar_not_connected"
        ) from exc
    db.commit()
    return SyncSummaryOut(
        created=counter.created, updated=counter.updated, deleted=counter.deleted
    )
