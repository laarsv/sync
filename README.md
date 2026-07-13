# Sync — self-hosted Google Calendar mirroring

Sync is a small self-hosted web tool that mirrors events between Google
Calendars. You log in with Google, connect your account, and create directed
**sync pairs** — each pair copies events from a source calendar into a target
calendar, either as a generic "busy" block or with full details.

Typical use: mirror a private calendar into a shared team calendar so colleagues
see when you're blocked, without exposing the details.

> The web UI is in German. Everything else (config, docs) is language-neutral.

## Features

- **Multi-user**, Google login. Optionally restricted to one Google Workspace
  domain, or open to any Google account.
- **Directed sync pairs**: source → target, `busy` or `full` detail, per-pair
  on/off. Two directions = two pairs (one-click "also create the reverse").
- **Per-pair options**: origin tag prefix (e.g. `(P) Meeting`), event color,
  and a *confidential* toggle (mirror is `private`: you see details, others with
  calendar access only see "busy").
- **Skips free/declined events** so they don't block time in the target.
- **Robust sync engine**: incremental `syncToken` polling, loop protection,
  idempotent updates, delete propagation, recurring-event handling, Google
  rate-limit backoff. Never sends e-mail invites (`sendUpdates=none`).
- **Encrypted tokens at rest** (Fernet). Optional reconnect e-mail (Brevo) when
  Google access is revoked.
- Manual "sync now" runs in the background; sync history and an admin overview
  in the UI.

## Requirements

- A server with Docker + Docker Compose.
- A domain name pointing at that server (for the default setup, ports 80/443).
- A Google Cloud project with an OAuth client and the Calendar API enabled.

## Quick start (self-contained, automatic HTTPS)

The default `docker-compose.yml` runs the backend, the frontend, and a bundled
Caddy that obtains a Let's Encrypt certificate for your domain automatically.

```bash
git clone https://github.com/<you>/sync.git && cd sync
cp .env.example .env
# edit .env: set DOMAIN, APP_SECRET, the Google credentials and the Fernet key
docker compose up -d --build
```

Then open `https://<your-domain>`.

Point your domain's DNS A-record at the server first, and make sure ports 80
and 443 are reachable so Caddy can issue the certificate.

## Google Cloud setup (once)

1. Create/choose a project at <https://console.cloud.google.com>.
2. **Enable the Google Calendar API** (APIs & Services → Library).
3. **Create an OAuth client** (APIs & Services → Credentials → OAuth client ID,
   type *Web application*).
4. Add two **Authorized redirect URIs** (replace with your domain):
   - `https://your-domain/api/auth/google/callback` (login)
   - `https://your-domain/calendar/callback` (calendar consent)
5. On the OAuth consent screen: if you restrict to a Workspace domain, set the
   publishing status to **Internal**; otherwise you may need to add test users
   or verify the app for the sensitive Calendar scopes.
6. Put the client ID/secret into `.env`.

Scopes used: `openid email profile` (login) plus `calendar.events` and
`calendar.readonly` (calendar). No Gmail/Drive scopes.

## Configuration (`.env`)

| Variable | Required | Notes |
| --- | --- | --- |
| `DOMAIN` | yes (default setup) | Public host, no scheme. Drives base URL, redirects, CORS, Caddy. |
| `APP_SECRET` | yes | `openssl rand -hex 32` |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | yes | From Google Cloud |
| `GOOGLE_TOKEN_ENCRYPTION_KEY` | yes | Fernet key (see `.env.example`) |
| `ALLOWED_EMAIL_DOMAIN` | no | Restrict login to one Workspace domain. Empty = any verified Google account. |
| `INITIAL_ADMIN_EMAIL` | no | Becomes admin. Empty = the first user to log in becomes admin. |
| `BREVO_API_KEY` / `_FROM_EMAIL` | no | Reconnect e-mail. Empty = disabled. |
| `SYNC_POLL_INTERVAL_MINUTES` | no | Default 3. |

Redirect URIs and CORS are derived from `DOMAIN`/`APP_BASE_URL` automatically;
override them only if you need to.

## Behind an existing reverse proxy

If you already run a central reverse proxy (e.g. one Caddy for several apps on a
shared Docker network), use `docker-compose.prod.yml` instead. It publishes no
ports and joins an external network named `proxy`; route your proxy to the
`sync-api` (`:8000`) and `sync-web` (`:80`) containers — see
`Caddyfile.snippet`. In that setup set `APP_BASE_URL`, `DATABASE_URL` and
`COOKIE_SECURE` in `.env` (see `.env.example`).

## Local development

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env with: APP_BASE_URL=http://localhost:5173, COOKIE_SECURE=false,
#            DATABASE_URL=sqlite:///./data/sync.db, plus Google creds + Fernet key
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

## Updating

```bash
git pull
docker compose up -d --build
```

Schema changes are applied automatically on start (create-tables + small
idempotent SQLite migrations).

## Data & backups

SQLite lives in the `sync_data` volume (self-contained setup) or under your
mounted data path (external-proxy setup), in WAL mode (`.db`, `.db-wal`,
`.db-shm`). Back up the whole data directory/volume. The token-encryption key
lives only in `.env` — a database backup alone contains ciphertext only, so
keep the key safe and separate.

## Tech stack

FastAPI + SQLAlchemy (SQLite) + APScheduler; Google Calendar REST via `httpx`
(no SDK). React + Vite + Tailwind SPA served by nginx. Caddy for TLS/routing.
See `DESIGN.md` for the design system.

## License

See [LICENSE](LICENSE).
