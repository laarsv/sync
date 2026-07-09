from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SQLite-Pfad. In Prod absolut auf das Volume: sqlite:////app/data/sync.db
    DATABASE_URL: str = "sqlite:///./data/sync.db"

    # Signatur des Session-Cookies (Starlette SessionMiddleware) UND des
    # kurzlebigen OAuth-state (jose JWT). Generieren mit: openssl rand -hex 32
    APP_SECRET: str = "changeme-openssl-rand-hex-32"
    # Session-Cookie "Secure"-Flag. Prod: True (HTTPS). Lokal ueber http://localhost
    # auf False setzen, sonst speichert der Browser das Cookie ggf. nicht.
    COOKIE_SECURE: bool = True

    # Ein gemeinsamer Google-OAuth-Client fuer Login UND Calendar-Consent -
    # unterschiedliche Redirects/Scopes, gleiche client_id/secret.
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    # Login-Redirect (server-side, Authlib) -> Backend-Route.
    GOOGLE_OAUTH_REDIRECT_URI: str = "https://sync.vrwb.de/api/auth/google/callback"
    # Calendar-Consent-Redirect (frontend-driven) -> SPA-Route.
    GOOGLE_CALENDAR_REDIRECT_URI: str = "https://sync.vrwb.de/calendar/callback"

    # Fernet-Key (32 url-safe base64 Bytes) fuer Encryption der Google-OAuth-Tokens
    # at-rest. Generieren mit:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Wenn leer, ist die Kalender-Verbindung deaktiviert und liefert einen klaren Fehler.
    GOOGLE_TOKEN_ENCRYPTION_KEY: str = ""

    # Login/Consent ausschliesslich fuer diese Google-Workspace-Domain.
    ALLOWED_EMAIL_DOMAIN: str = "koenigswege.com"
    # Diese Adresse wird beim ersten Login automatisch Admin.
    INITIAL_ADMIN_EMAIL: str = "lars.verwiebe@koenigswege.com"

    CORS_ORIGINS: str = "https://sync.vrwb.de,http://localhost:5173"
    APP_BASE_URL: str = "https://sync.vrwb.de"

    # Sync-Engine.
    SYNC_POLL_INTERVAL_MINUTES: int = 3
    # Wie weit in die Vergangenheit beim Full-Sync (timeMin). Aeltere Quell-Events
    # werden nicht gespiegelt; deren Mirrors altern einfach aus.
    SYNC_BACKFILL_DAYS: int = 30
    # Erzwungener Full-Resync-Turnus (rollt das timeMin-Fenster vor, faengt
    # verlorene syncToken-Kontexte ab).
    SYNC_FULL_RESYNC_HOURS: int = 24

    # NUR LOKAL: passwortloser Dev-Login (jede @<Domain>-Adresse). Prod: False.
    DEV_LOGIN: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
