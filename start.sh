#!/bin/sh
# Start the local OMEGA lab without overwriting existing configuration or data.
set -eu
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  printf 'Docker is not installed. Install Docker Desktop, then try again.\n' >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  printf 'Docker is not running. Start Docker Desktop, then try again.\n' >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  printf 'Docker Compose v2 is required.\n' >&2
  exit 1
fi
if [ ! -e .env ]; then
  cp .env.example .env
  printf 'Created .env from .env.example.\n'
fi
printf 'Building and starting OMEGA...\n'
docker compose -p omega up -d --build
printf '\nContainer status:\n'
docker compose -p omega ps
printf '\nDashboard: http://localhost:5173\nAPI docs:   http://localhost:8001/docs\n'
if [ "${1:-}" != '--no-browser' ] && command -v open >/dev/null 2>&1; then
  open 'http://localhost:5173' || true
fi
