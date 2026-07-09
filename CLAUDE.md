# CLAUDE.md — Sync

Google-Kalender-Sync-Tool fürs Königswege-Team, `sync.vrwb.de`. Eigener Auftritt
in Royal-Blau (`#2947c9`), UI **strikt** nach `DESIGN.md`.

## Stack / Muster
- Backend: FastAPI + SQLAlchemy (SQLite), APScheduler. Google Calendar REST via
  httpx (kein SDK). Login: Google OIDC (Authlib, Session-Cookie, nur
  `@koenigswege.com`). Calendar-OAuth-Token pro User, Fernet-verschlüsselt
  (`GOOGLE_TOKEN_ENCRYPTION_KEY`). Muster übernommen aus `financeandcoffee-shop`.
- Frontend: React + Vite + Tailwind, nginx-SPA. Deploy-Muster aus `relay`/`tab`.
- Prod: 2 Container (`sync-api`, `sync-web`) am externen Docker-Netz `proxy`,
  Caddy routet per **explizitem container_name**. Daten unter
  `/opt/appdata/sync/data`, Checkout `/opt/appdata/sync-app`.

## Nicht anfassen ohne Grund
- `services/sync_engine.py` — Loop-Schutz (`syncSource`-Marker), Idempotenz
  (`event_mappings`), Delete-Propagation (syncToken-Deltas, `status=cancelled`),
  `sendUpdates=none` (nie Invites), Busy-Modus (keine Details/Teilnehmer).
- `auth/google_calendar.py` — Token-Exchange/Refresh/Revoke + Fernet.

## Deploy
`./deploy.sh` auf dem Host (git pull + `docker compose -f docker-compose.prod.yml
up -d --build`). Kein CI.
