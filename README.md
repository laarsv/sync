# Sync — Google-Kalender-Sync fürs Königswege-Team

Multi-User-Webtool unter **sync.vrwb.de**. Jeder Nutzer verbindet seinen
`@koenigswege.com`-Google-Account per OAuth und legt gerichtete **Sync-Paare**
an (Quell-Kalender → Ziel-Kalender). Ein Paar spiegelt Termine – wahlweise als
generischen „Belegt"-Block oder mit vollen Details.

Private Kalender kommen **nicht** per eigenem Login rein, sondern per
Google-nativer Freigabe an den koenigswege-Account und erscheinen dann in der
Kalenderliste.

## Architektur

- **backend/** — FastAPI + SQLAlchemy (SQLite), APScheduler. Google Calendar
  REST von Hand über httpx (kein SDK). Login via Google OIDC (Authlib,
  Session-Cookie, nur `@koenigswege.com`). Calendar-Tokens Fernet-verschlüsselt
  at-rest (ein Token pro User).
- **frontend/** — React + Vite + Tailwind (Royal-Blau), nginx-SPA. Siehe
  `DESIGN.md`.
- **Caddy** (zentral, extern) routet `sync.vrwb.de`: `/api/*` → `sync-api:8000`,
  Rest → `sync-web:80` (explizite Container-Namen).

## Sync-Engine (Kern: `backend/app/services/sync_engine.py`)

Change-Detection per **Polling + `syncToken`** (`singleEvents=true`), alle
`SYNC_POLL_INTERVAL_MINUTES`. Behandelte Landminen:

- **Loop-Schutz** — jedes Spiegel-Event trägt
  `extendedProperties.private.syncSource=kw-sync`; markierte Events werden als
  Quelle ignoriert (nie eine Kopie erneut spiegeln).
- **Idempotenz** — `event_mappings` (UNIQUE `pair+source_event_id`): Updates
  treffen dasselbe Ziel-Event.
- **Delete-Propagation** — `status=cancelled`/gelöscht aus den syncToken-Deltas
  → Spiegel-Event wird entfernt.
- **Serientermine** — `singleEvents=true`: Instanzen einzeln, Ausnahmen/Absagen
  als eigene Einträge, gematcht über die stabile Instanz-ID.
- **Busy-Modus** — generischer Titel, keine Details, keine Teilnehmer.
- **Keine Invites** — jeder Schreib-/Löschvorgang mit `sendUpdates=none`.

## Lokal entwickeln

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env    # lokale Werte: sqlite:///./data/sync.db, COOKIE_SECURE=false
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev      # http://localhost:5173, /api -> :8000 (Vite-Proxy)
```

## Google Cloud (einmalig)

OAuth-Client (Typ **Web**), Publishing-Status **Internal**. Scopes:
`calendar.events` + `calendar.readonly` (Login zusätzlich `openid email
profile`). Zwei Redirect-URIs eintragen:

- `https://sync.vrwb.de/api/auth/google/callback` (Login)
- `https://sync.vrwb.de/calendar/callback` (Calendar-Consent)

## Deploy (Host, Hetzner)

```bash
# einmalig
mkdir -p /opt/appdata/sync/data
git clone <repo> /opt/appdata/sync-app && cd /opt/appdata/sync-app
cp .env.example .env && nano .env      # Secrets füllen (openssl rand -hex 32, Fernet-Key)
# Caddyfile.snippet ans zentrale /opt/appdata/caddy/Caddyfile anhängen + Caddy reload
# DNS: A-Record sync.vrwb.de -> Host

./deploy.sh    # git pull + docker compose up -d --build
```

Daten (SQLite + WAL) liegen unter `/opt/appdata/sync/data` — ins Server-Backup
aufnehmen. Der `GOOGLE_TOKEN_ENCRYPTION_KEY` liegt **getrennt** in `.env`
(chmod 600); ein Backup der DB allein enthält nur Chiffretext.
