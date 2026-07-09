from authlib.integrations.starlette_client import OAuth

from .config import settings

oauth = OAuth()

# Login-Client: OpenID Connect, nur email/profile. Kein Kalender-/Drive-Scope.
# Der Calendar-Consent laeuft ueber einen eigenen, frontend-getriebenen Flow
# (siehe auth/google_calendar.py) - mit demselben OAuth-Client, aber anderem
# Redirect + Scopes.
oauth.register(
    name="google",
    client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
    client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
