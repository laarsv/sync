"""Transaktionsmails ueber Brevo (nur wenn konfiguriert)."""

from __future__ import annotations

import logging

import httpx

from ..config import settings
from ..models import User

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


async def send_email(to_email: str, to_name: str | None, subject: str, html: str) -> bool:
    if not settings.BREVO_API_KEY or not settings.BREVO_FROM_EMAIL:
        logger.info(
            "Brevo nicht konfiguriert - Mail '%s' an %s uebersprungen", subject, to_email
        )
        return False
    payload = {
        "sender": {"name": settings.BREVO_FROM_NAME, "email": settings.BREVO_FROM_EMAIL},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                BREVO_URL,
                headers={"api-key": settings.BREVO_API_KEY, "content-type": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.warning("Brevo-Request fehlgeschlagen: %s", exc)
        return False
    if resp.status_code >= 300:
        logger.warning("Brevo-Mail fehlgeschlagen: %s %s", resp.status_code, resp.text[:200])
        return False
    return True


def _reconnect_html(name: str | None, link: str) -> str:
    hallo = f"Hallo {name}," if name else "Hallo,"
    return f"""\
<div style="font-family:Roboto,system-ui,sans-serif;color:#161a24;max-width:520px">
  <p>{hallo}</p>
  <p>deine Google-Kalender-Verbindung in <b>Sync</b> wurde getrennt
     (Zugriff widerrufen oder abgelaufen). Der Kalender-Sync <b>pausiert</b>,
     bis du dich neu verbindest.</p>
  <p style="margin:24px 0">
    <a href="{link}"
       style="background:#2947c9;color:#ffffff;text-decoration:none;
              padding:12px 22px;border-radius:8px;font-weight:700;display:inline-block">
      Jetzt neu verbinden
    </a>
  </p>
  <p style="color:#161a24;opacity:.6;font-size:13px">Oder diesen Link oeffnen: {link}</p>
</div>"""


async def send_reconnect_email(user: User) -> bool:
    link = settings.APP_BASE_URL.rstrip("/") + "/connect"
    return await send_email(
        user.email,
        user.name,
        "Sync: Kalender-Verbindung abgelaufen - bitte neu verbinden",
        _reconnect_html(user.name, link),
    )
