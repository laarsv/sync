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
    # Redirect-URIs. Leer -> werden aus APP_BASE_URL abgeleitet (siehe unten).
    # Nur setzen, wenn du abweichende URIs brauchst.
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    GOOGLE_CALENDAR_REDIRECT_URI: str = ""

    # Fernet-Key (32 url-safe base64 Bytes) fuer Encryption der Google-OAuth-Tokens
    # at-rest. Generieren mit:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Wenn leer, ist die Kalender-Verbindung deaktiviert und liefert einen klaren Fehler.
    GOOGLE_TOKEN_ENCRYPTION_KEY: str = ""

    # Login-Beschraenkung auf eine Google-Workspace-Domain. LEER = jeder
    # verifizierte Google-Account darf sich anmelden (fuer Einzel-/Privatbetrieb).
    ALLOWED_EMAIL_DOMAIN: str = ""
    # Diese Adresse wird beim ersten Login automatisch Admin. Leer -> der ALLERERSTE
    # Nutzer, der sich anmeldet, wird Admin.
    INITIAL_ADMIN_EMAIL: str = ""

    # Oeffentliche Basis-URL der Instanz (z.B. https://sync.example.com). Steuert
    # Redirect-URIs, CORS und Mail-Links. Lokal: http://localhost:5173.
    APP_BASE_URL: str = "http://localhost:5173"
    # CORS-Origins (kommasepariert). Leer -> APP_BASE_URL.
    CORS_ORIGINS: str = ""

    # Brevo Transactional Mail (Reconnect-Benachrichtigung). Leer -> Mail aus.
    BREVO_API_KEY: str = ""
    BREVO_FROM_NAME: str = "Sync"
    BREVO_FROM_EMAIL: str = ""

    # Sync-Engine.
    SYNC_POLL_INTERVAL_MINUTES: int = 3
    # Wie weit in die Vergangenheit beim Full-Sync (timeMin). Aeltere Quell-Events
    # werden nicht gespiegelt; deren Mirrors altern einfach aus.
    SYNC_BACKFILL_DAYS: int = 30
    # Erzwungener Full-Resync-Turnus (rollt das timeMin-Fenster vor, faengt
    # verlorene syncToken-Kontexte ab).
    SYNC_FULL_RESYNC_HOURS: int = 24
    # Kleine Pause nach jedem Google-Schreibvorgang (ms), um Rate-Limits zu
    # glaetten. 0 = aus. Bei anhaltendem rateLimitExceeded hochsetzen.
    SYNC_WRITE_PAUSE_MS: int = 60

    # NUR LOKAL: passwortloser Dev-Login (jede @<Domain>-Adresse). Prod: False.
    DEV_LOGIN: bool = False

    @property
    def base_url(self) -> str:
        return self.APP_BASE_URL.rstrip("/")

    @property
    def login_redirect_uri(self) -> str:
        return self.GOOGLE_OAUTH_REDIRECT_URI or f"{self.base_url}/api/auth/google/callback"

    @property
    def calendar_redirect_uri(self) -> str:
        return self.GOOGLE_CALENDAR_REDIRECT_URI or f"{self.base_url}/calendar/callback"

    @property
    def cors_origins_list(self) -> List[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return origins or [self.base_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
