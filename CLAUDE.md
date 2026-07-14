# CLAUDE.md — Sync

Self-hosted Google Calendar mirroring tool. UI in German; UI strictly follows
`DESIGN.md` (royal blue, `#2947c9`).

Brand: **VRWB CI v1.0**. Tool mark = standalone product lockup **`vrwb_sync`**
(`frontend/src/components/Wordmark.jsx` — never rebuild inline): `vrwb` Roboto 900
(−0.045em), `_sync` Royal, toolname Roboto Mono 500 (0.83×, −0.01em), always
lowercase; on ink `_sync` in Royal Soft. Favicon `s_` on Royal
(`public/favicon.svg`). Roboto + Roboto Mono self-hosted, no CDN. Never set
"Sync"/"SYNC" as the mark. Source + details: `DESIGN.md §1b`.

## Stack / layout
- Backend (`backend/app`): FastAPI + SQLAlchemy (SQLite) + APScheduler. Google
  Calendar REST via `httpx` (no SDK). Login: Google OIDC (Authlib, session
  cookie). Per-user Google token, Fernet-encrypted at rest
  (`GOOGLE_TOKEN_ENCRYPTION_KEY`).
- Frontend (`frontend/`): React + Vite + Tailwind, nginx-served SPA.
- Deploy: `docker-compose.yml` (self-contained + bundled Caddy) or
  `docker-compose.prod.yml` (behind an existing reverse proxy).

## Don't touch without care
- `services/sync_engine.py` — loop protection (`syncSource` marker), idempotency
  (`event_mappings`), delete propagation (syncToken deltas, `status=cancelled`),
  skip free/declined events, `sendUpdates=none` (never send invites), busy mode,
  short-held SQLite write locks (commit per source event), per-user DB run lock.
- `auth/google_calendar.py` — token exchange/refresh/revoke + Fernet.

## Config
Everything is env-driven; base URL, redirect URIs and CORS derive from
`APP_BASE_URL`/`DOMAIN`. See `.env.example`. No hardcoded domains or org data.

## Conventions
- Backend comments are in German; keep new code consistent with the surrounding
  style.
- Commit messages: concise; describe the change.
