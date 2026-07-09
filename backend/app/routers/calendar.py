from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import google_calendar as gcal
from ..config import settings
from ..deps import get_current_user, get_db
from ..models import User
from ..schemas import (
    AuthorizeUrlOut,
    CalendarCallbackIn,
    CalendarOut,
    CalendarStatusOut,
)
from ..services import google_calendar as svc

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status", response_model=CalendarStatusOut)
def calendar_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> CalendarStatusOut:
    if not settings.GOOGLE_TOKEN_ENCRYPTION_KEY.strip():
        return CalendarStatusOut(connected=False, scopes=[])
    creds = gcal.get_credentials(db, current_user)
    if creds is None:
        return CalendarStatusOut(connected=False, scopes=[])
    return CalendarStatusOut(
        connected=gcal.is_connected(db, current_user),
        google_email=creds.google_email,
        scopes=(creds.scopes or "").split(),
    )


@router.get("/authorize-url", response_model=AuthorizeUrlOut)
def authorize_url(
    redirect_uri: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> AuthorizeUrlOut:
    try:
        url = gcal.build_authorize_url(current_user, redirect_uri)
    except gcal.EncryptionKeyMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="calendar_not_configured",
        ) from exc
    except gcal.CalendarAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return AuthorizeUrlOut(auth_url=url)


@router.post("/callback", response_model=CalendarStatusOut)
async def callback(
    payload: CalendarCallbackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarStatusOut:
    try:
        gcal.validate_state(payload.state, current_user)
        creds = await gcal.store_credentials_from_code(
            db, current_user, payload.code, payload.redirect_uri
        )
    except gcal.EncryptionKeyMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="calendar_not_configured",
        ) from exc
    except gcal.CalendarAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    db.commit()
    return CalendarStatusOut(
        connected=True,
        google_email=creds.google_email,
        scopes=(creds.scopes or "").split(),
    )


@router.post("/disconnect")
async def disconnect(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await gcal.disconnect(db, current_user)
    db.commit()
    return {"ok": True}


@router.get("/calendars", response_model=List[CalendarOut])
async def list_calendars(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> List[CalendarOut]:
    try:
        token = await gcal.get_valid_access_token(db, current_user)
    except gcal.CalendarNotConnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="calendar_not_connected"
        ) from exc
    except gcal.CalendarAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        items = await svc.list_calendar_list(token)
    except svc.CalendarApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        ) from exc
    finally:
        # Token-Refresh kann creds aktualisiert haben.
        db.commit()

    out = [
        CalendarOut(
            id=i["id"],
            summary=i.get("summary") or i.get("summaryOverride") or i["id"],
            primary=bool(i.get("primary")),
            access_role=i.get("accessRole"),
            background_color=i.get("backgroundColor"),
        )
        for i in items
    ]
    # Primaerkalender zuerst, dann alphabetisch.
    out.sort(key=lambda c: (not c.primary, c.summary.lower()))
    return out
