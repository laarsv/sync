from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import get_current_user, get_db
from ..models import User, UserRole
from ..oauth import oauth
from ..schemas import MeOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _redirect_login(error: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?error={error}", status_code=302)


@router.get("/google/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(
        request, settings.GOOGLE_OAUTH_REDIRECT_URI
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:  # noqa: BLE001
        return _redirect_login("oauth_failed")

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower().strip()
    name = userinfo.get("name") or (email.split("@")[0] if email else "")
    email_verified = bool(userinfo.get("email_verified", False))
    hd = (userinfo.get("hd") or "").lower().strip()
    google_sub = userinfo.get("sub")
    picture = userinfo.get("picture")

    # OAuth-Haertung: verifizierte Mail UND hd-Claim UND E-Mail-Domain muessen
    # exakt auf die erlaubte Workspace-Domain passen.
    if not email or not email_verified:
        return _redirect_login("email_unverified")
    allowed = settings.ALLOWED_EMAIL_DOMAIN.lower().strip()
    email_domain = email.split("@")[-1] if "@" in email else ""
    if not allowed or hd != allowed or email_domain != allowed:
        return _redirect_login("wrong_domain")

    is_admin_email = email == settings.INITIAL_ADMIN_EMAIL.lower().strip()

    user = db.query(User).filter(User.google_sub == google_sub).one_or_none()
    if user is None:
        user = db.query(User).filter(func.lower(User.email) == email).one_or_none()

    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            name=name,
            picture_url=picture,
            role=UserRole.admin if is_admin_email else UserRole.user,
        )
        db.add(user)
        db.flush()
    else:
        user.google_sub = google_sub or user.google_sub
        user.email = email
        if name:
            user.name = name
        if picture:
            user.picture_url = picture
        if is_admin_email and user.role != UserRole.admin:
            user.role = UserRole.admin

    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    request.session["user_id"] = user.id
    db.commit()
    return RedirectResponse(url="/", status_code=302)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
def me(current_user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        photo_url=current_user.picture_url,
        role=current_user.role.value,
        is_admin=current_user.is_admin,
    )
