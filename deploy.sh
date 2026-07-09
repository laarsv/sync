#!/usr/bin/env bash
set -euo pipefail

# Laeuft AUF dem Host im Code-Verzeichnis (/opt/appdata/sync-app).
# Voraussetzungen: git-Checkout vorhanden, .env gefuellt, externes Docker-Netz
# "proxy" existiert, Caddyfile.snippet ins zentrale Caddyfile eingebunden.

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "FEHLER: .env fehlt. Erst 'cp .env.example .env' und ausfuellen." >&2
  exit 1
fi

echo "==> Datenverzeichnis sicherstellen"
mkdir -p /opt/appdata/sync/data

echo "==> git pull"
git pull --ff-only

echo "==> docker compose build & up"
docker compose -f docker-compose.prod.yml up -d --build

echo "==> Status"
docker compose -f docker-compose.prod.yml ps
