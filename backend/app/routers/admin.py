from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import google_calendar as gcal
from ..deps import get_db, require_admin
from ..models import GoogleOAuthCredentials, SyncPair, SyncRun, User
from ..schemas import AdminUserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview", response_model=List[AdminUserOut])
def overview(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> List[AdminUserOut]:
    """Team-Uebersicht: Verbindungs- und Sync-Status aller Nutzer (nur Admin)."""
    out: List[AdminUserOut] = []
    users = db.query(User).order_by(User.email.asc()).all()
    for u in users:
        creds = (
            db.query(GoogleOAuthCredentials).filter_by(user_id=u.id).one_or_none()
        )
        connected = (
            creds is not None
            and bool(creds.refresh_token_enc)
            and gcal.CALENDAR_EVENTS_SCOPE in (creds.scopes or "").split()
        )
        pair_count = (
            db.query(func.count(SyncPair.id)).filter_by(owner_user_id=u.id).scalar() or 0
        )
        active_count = (
            db.query(func.count(SyncPair.id))
            .filter_by(owner_user_id=u.id, active=True)
            .scalar()
            or 0
        )
        last = (
            db.query(SyncRun)
            .filter_by(user_id=u.id)
            .order_by(SyncRun.id.desc())
            .first()
        )
        if last is None:
            last_status, last_run_at, last_error = "never", None, None
        else:
            last_run_at = last.finished_at or last.started_at
            last_error = last.error
            last_status = "ok" if last.ok else "error"

        out.append(
            AdminUserOut(
                id=u.id,
                email=u.email,
                name=u.name,
                is_admin=u.is_admin,
                connected=connected,
                google_email=creds.google_email if creds else None,
                pair_count=pair_count,
                active_pair_count=active_count,
                last_run_at=last_run_at,
                last_status=last_status,
                last_error=last_error,
            )
        )
    return out
