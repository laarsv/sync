"""Frontend-getriebener Google-OAuth-Flow fuer die Calendar-Scopes.

Eigener Redirect-URI, eigene Scopes, eigene Token-Persistenz. Refresh- und
Access-Token werden mit Fernet at-rest verschluesselt in
`google_oauth_credentials` abgelegt.

Der `state` wird mit APP_SECRET (jose JWT, HS256) signiert - CSRF-Schutz +
Bindung an den eingeloggten User.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import settings
from ..models import GoogleOAuthCredentials, User

logger = logging.getLogger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Events lesen/schreiben/loeschen + Kalenderliste/Events lesen (fuer Dropdowns).
# KEINE Gmail/Drive-Scopes.
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
REQUIRED_SCOPES = (CALENDAR_EVENTS_SCOPE,)
AUTHORIZE_SCOPES = (
    "openid",
    "email",
    CALENDAR_EVENTS_SCOPE,
    CALENDAR_READONLY_SCOPE,
)

STATE_TTL_SECONDS = 600
_STATE_ALG = "HS256"


class CalendarAuthError(Exception):
    """Wird in den Routern auf saubere HTTP-Codes gemappt."""


class CalendarNotConnectedError(CalendarAuthError):
    pass


class CalendarRevokedError(CalendarNotConnectedError):
    """Token war vorhanden, wurde aber von Google widerrufen -> Creds geloescht.
    Ausloeser fuer die einmalige Reconnect-Benachrichtigung."""


class EncryptionKeyMissingError(CalendarAuthError):
    pass


# ---------- Fernet-Encryption ----------


def _get_fernet() -> Fernet:
    key = settings.GOOGLE_TOKEN_ENCRYPTION_KEY.strip()
    if not key:
        raise EncryptionKeyMissingError(
            "GOOGLE_TOKEN_ENCRYPTION_KEY ist nicht gesetzt. Generieren: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise EncryptionKeyMissingError(
            f"GOOGLE_TOKEN_ENCRYPTION_KEY ist kein gueltiger Fernet-Key: {exc}"
        ) from exc


def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise CalendarAuthError("Token-Entschluesselung fehlgeschlagen") from exc


# ---------- State (CSRF-Schutz) ----------


def issue_state(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "purpose": "calendar_oauth",
        "nonce": uuid.uuid4().hex,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=STATE_TTL_SECONDS)).timestamp()
        ),
    }
    return jwt.encode(payload, settings.APP_SECRET, algorithm=_STATE_ALG)


def validate_state(state: str, user: User) -> None:
    try:
        claims = jwt.decode(state, settings.APP_SECRET, algorithms=[_STATE_ALG])
    except JWTError as exc:
        raise CalendarAuthError(f"Ungueltiger state-Parameter: {exc}") from exc
    if claims.get("purpose") != "calendar_oauth":
        raise CalendarAuthError("State hat den falschen Zweck")
    if claims.get("sub") != str(user.id):
        raise CalendarAuthError("State gehoert nicht zum aktuellen Nutzer")


# ---------- Authorize-URL ----------


def build_authorize_url(user: User, redirect_uri: Optional[str] = None) -> str:
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise CalendarAuthError("GOOGLE_OAUTH_CLIENT_ID nicht konfiguriert")
    _get_fernet()  # frueh validieren - sonst klemmt der Callback
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri or settings.calendar_redirect_uri,
        "response_type": "code",
        "scope": " ".join(AUTHORIZE_SCOPES),
        "access_type": "offline",
        # `consent` erzwingt das Refresh-Token (Google liefert es sonst nur einmalig).
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": issue_state(user),
        "login_hint": user.email,
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


# ---------- Token-Exchange + Refresh ----------


async def _exchange_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    data = {
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise CalendarAuthError(
            f"Calendar token exchange failed: {resp.status_code} {resp.text}"
        )
    return resp.json()


async def _refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    data = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=data)
    if resp.status_code != 200:
        # invalid_grant -> User hat App in seinem Google-Account widerrufen
        raise CalendarAuthError(f"Refresh failed: {resp.status_code} {resp.text}")
    return resp.json()


async def _fetch_email(access_token: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 200:
            return (resp.json().get("email") or "").lower() or None
    except httpx.HTTPError:
        logger.warning("Userinfo-Fetch nach Calendar-Auth fehlgeschlagen", exc_info=True)
    return None


# ---------- Persistenz ----------


async def store_credentials_from_code(
    db: Session, user: User, code: str, redirect_uri: str
) -> GoogleOAuthCredentials:
    token_response = await _exchange_code(code, redirect_uri)
    refresh_token = token_response.get("refresh_token")
    access_token = token_response.get("access_token")
    granted_scopes = token_response.get("scope", "")
    expires_in = int(token_response.get("expires_in") or 0)

    if not refresh_token:
        raise CalendarAuthError(
            "Google hat kein refresh_token geliefert. Bitte unter "
            "https://myaccount.google.com/permissions Zugriff entfernen und "
            "erneut verbinden."
        )

    if CALENDAR_EVENTS_SCOPE not in granted_scopes.split():
        raise CalendarAuthError(
            "Calendar-Scope wurde nicht gewaehrt. Bitte beim Consent die "
            "Checkboxen setzen."
        )

    google_email = await _fetch_email(access_token) if access_token else None

    expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(seconds=max(0, expires_in - 30))
        if expires_in
        else None
    )

    existing = (
        db.query(GoogleOAuthCredentials)
        .filter(GoogleOAuthCredentials.user_id == user.id)
        .one_or_none()
    )
    if existing is None:
        existing = GoogleOAuthCredentials(user_id=user.id, refresh_token_enc="")
        db.add(existing)

    existing.refresh_token_enc = _encrypt(refresh_token)
    existing.access_token_enc = _encrypt(access_token) if access_token else None
    existing.access_token_expires_at = expires_at
    existing.scopes = granted_scopes
    existing.google_email = google_email
    db.flush()
    return existing


def get_credentials(db: Session, user: User) -> Optional[GoogleOAuthCredentials]:
    return (
        db.query(GoogleOAuthCredentials)
        .filter(GoogleOAuthCredentials.user_id == user.id)
        .one_or_none()
    )


def is_connected(db: Session, user: User) -> bool:
    creds = get_credentials(db, user)
    if creds is None or not creds.refresh_token_enc:
        return False
    return CALENDAR_EVENTS_SCOPE in (creds.scopes or "").split()


async def get_valid_access_token(db: Session, user: User) -> str:
    creds = get_credentials(db, user)
    if creds is None or not creds.refresh_token_enc:
        raise CalendarNotConnectedError("Kein Calendar-Token fuer diesen Nutzer")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        creds.access_token_enc
        and creds.access_token_expires_at
        and creds.access_token_expires_at - timedelta(seconds=60) > now
    ):
        return _decrypt(creds.access_token_enc)

    refresh_token = _decrypt(creds.refresh_token_enc)
    try:
        token_response = await _refresh_access_token(refresh_token)
    except CalendarAuthError:
        # Refresh-Token revoked/abgelaufen - Credentials weg, User muss neu verbinden.
        db.delete(creds)
        db.flush()
        raise CalendarRevokedError(
            "Google hat den Zugriff widerrufen. Bitte erneut verbinden."
        )

    access_token = token_response.get("access_token")
    expires_in = int(token_response.get("expires_in") or 0)
    if not access_token:
        raise CalendarAuthError("Kein access_token im Refresh-Response")

    creds.access_token_enc = _encrypt(access_token)
    creds.access_token_expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(seconds=max(0, expires_in - 30))
        if expires_in
        else None
    )
    new_scope = token_response.get("scope")
    if new_scope:
        creds.scopes = new_scope
    db.flush()
    return access_token


async def disconnect(db: Session, user: User) -> None:
    creds = get_credentials(db, user)
    if creds is None:
        return
    # Best-effort revoke beim Google-Endpoint (kein Hard-Fail).
    try:
        refresh_token = _decrypt(creds.refresh_token_enc)
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(GOOGLE_REVOKE_URL, data={"token": refresh_token})
    except Exception:  # noqa: BLE001
        logger.info("Google revoke best-effort fehlgeschlagen", exc_info=True)
    db.delete(creds)
    db.flush()
