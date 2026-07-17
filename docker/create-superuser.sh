#!/bin/bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-devmind}
ACTIVE_COLOR="$(cat .active_color 2>/dev/null || echo blue)"
BACKEND_SERVICE=${BACKEND_SERVICE:-backend-api-${ACTIVE_COLOR}}

docker compose \
    -p "$COMPOSE_PROJECT_NAME" \
    -f "$COMPOSE_FILE" \
    run --rm "$BACKEND_SERVICE" create-superuser
