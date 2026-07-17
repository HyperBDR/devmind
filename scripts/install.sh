#!/bin/bash
# Install or upgrade DevMind with single-node blue/green deployment.
set -euo pipefail

BACKEND_IMAGE_REPO="${BACKEND_IMAGE_REPO:-registry.cn-beijing.aliyuncs.com/hypermotion_dockers/devmind-backend}"
FRONTEND_IMAGE_REPO="${FRONTEND_IMAGE_REPO:-registry.cn-beijing.aliyuncs.com/hypermotion_dockers/devmind-frontend}"

LOCAL_MODE=false
if [ "${1:-}" = "--local" ]; then
    LOCAL_MODE=true
    shift
fi

if [ "$LOCAL_MODE" = "true" ]; then
    GIT_REF="${1:-local}"
else
    GIT_REF="${1:?Usage: install.sh <git-ref> or install.sh --local [tag]}"
fi

IMAGE_TAG="${DEPLOY_APP_VERSION:-${GIT_REF#v}}"
DEPLOY_PATH="${DEPLOY_PATH:-$(pwd)}"
POST_SWITCH_OBSERVE_SECONDS="${POST_SWITCH_OBSERVE_SECONDS:-30}"

log() { echo -e "\033[1;36m[install]\033[0m $*"; }
die() { echo -e "\033[1;31m[install] ERROR:\033[0m $*" >&2; exit 1; }

cd "$DEPLOY_PATH"

LOCK_FILE="/tmp/devmind-install.lock"
MAX_WAIT=300
WAITED=0
while ! (set -o noclobber; echo "$$ $(date)" > "$LOCK_FILE") 2>/dev/null; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        log "Lock $LOCK_FILE still held after ${MAX_WAIT}s; taking it over"
        echo "$$ $(date)" > "$LOCK_FILE"
        break
    fi
    log "Another install is running, waiting... (${WAITED}s)"
    sleep 5
    WAITED=$((WAITED + 5))
done
trap 'rm -f "$LOCK_FILE"' EXIT

read_dotenv_value() {
    local key="$1"
    local line value
    [ -f "$DEPLOY_PATH/.env" ] || return 0
    line="$(
        grep -E "^(export[[:space:]]+)?${key}=" "$DEPLOY_PATH/.env" \
            | tail -1 || true
    )"
    [ -n "$line" ] || return 0
    line="${line#export }"
    value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf "%s" "$value"
}

ENV_DEPLOY_REPO="$(read_dotenv_value DEPLOY_REPO)"
REPO="${DEPLOY_REPO:-${ENV_DEPLOY_REPO:-HyperBDR/devmind}}"
ENV_DEPLOY_PRUNE_OLD_IMAGES="$(
    read_dotenv_value DEPLOY_PRUNE_OLD_IMAGES
)"
DEPLOY_PRUNE_OLD_IMAGES="${DEPLOY_PRUNE_OLD_IMAGES:-${ENV_DEPLOY_PRUNE_OLD_IMAGES:-true}}"

AUTH_HEADER=()
ENV_DEPLOY_GITHUB_TOKEN="$(read_dotenv_value DEPLOY_GITHUB_TOKEN)"
DEPLOY_GITHUB_TOKEN="${DEPLOY_GITHUB_TOKEN:-$ENV_DEPLOY_GITHUB_TOKEN}"
if [ -n "$DEPLOY_GITHUB_TOKEN" ]; then
    AUTH_HEADER=(-H "Authorization: token ${DEPLOY_GITHUB_TOKEN}")
fi

ASSETS=(
    docker-compose.yml
    docker/nginx/conf.d/default.conf
    docker/nginx/upstream.conf.default
    docker/nginx/certs/README.md
    docker/create-superuser.sh
    docker/postgresql/etc/postgresql.conf
    docker/postgresql/initdb.d/000-create-databases.sql
    docker/postgresql/initdb.d/001-grant-schema-privileges.sh
    docker/postgresql/initdb.d/002-setup-log-permissions.sh
    env.sample
    scripts/install.sh
    scripts/devmindctl.sh
    scripts/lib/deploy-common.sh
)

fetch_asset() {
    local path="$1"
    local dest="$DEPLOY_PATH/$path"
    mkdir -p "$(dirname "$dest")"
    curl -fsSL "${AUTH_HEADER[@]}" \
        "https://raw.githubusercontent.com/${REPO}/${GIT_REF}/${path}" \
        -o "${dest}.tmp"
    mv "${dest}.tmp" "$dest"
}

if [ "$LOCAL_MODE" = "true" ]; then
    log "Local mode: using files already in $DEPLOY_PATH"
else
    log "Fetching deploy assets from ${REPO}@${GIT_REF}"
    for path in "${ASSETS[@]}"; do
        fetch_asset "$path"
    done
    chmod +x "$DEPLOY_PATH/scripts/install.sh" \
        "$DEPLOY_PATH/scripts/devmindctl.sh" \
        "$DEPLOY_PATH/scripts/lib/deploy-common.sh" \
        "$DEPLOY_PATH/docker/create-superuser.sh"
fi

if [ ! -f "$DEPLOY_PATH/.env" ]; then
    if [ -f "$DEPLOY_PATH/env.sample" ]; then
        cp "$DEPLOY_PATH/env.sample" "$DEPLOY_PATH/.env"
        chmod 600 "$DEPLOY_PATH/.env"
        log "Seeded $DEPLOY_PATH/.env from env.sample"
    fi
    die "Edit $DEPLOY_PATH/.env with real secrets, then re-run install.sh."
fi

bootstrap_runtime_state() {
    mkdir -p "$DEPLOY_PATH/docker/nginx/conf.d"
    if [ ! -f "$DEPLOY_PATH/docker/nginx/conf.d/upstream.conf" ]; then
        log "Initializing nginx upstream.conf with blue as active"
        cp "$DEPLOY_PATH/docker/nginx/upstream.conf.default" \
            "$DEPLOY_PATH/docker/nginx/conf.d/upstream.conf"
    fi

    if [ ! -f "$DEPLOY_PATH/.active_color" ]; then
        echo "blue" > "$DEPLOY_PATH/.active_color"
    fi

    local cert_dir="$DEPLOY_PATH/docker/nginx/certs"
    if [ ! -f "$cert_dir/nginx-selfsigned.crt" ] \
        || [ ! -f "$cert_dir/nginx-selfsigned.key" ]; then
        log "Generating a self-signed TLS certificate"
        mkdir -p "$cert_dir"
        docker run --rm -v "$cert_dir:/certs" alpine/openssl req -x509 \
            -newkey rsa:2048 -nodes -days 3650 \
            -keyout /certs/nginx-selfsigned.key \
            -out /certs/nginx-selfsigned.crt \
            -subj "/CN=${DOMAIN:-localhost}" \
            -addext "subjectAltName=DNS:${DOMAIN:-localhost},IP:127.0.0.1"
    fi
}
bootstrap_runtime_state

# shellcheck source=./lib/deploy-common.sh
source "$DEPLOY_PATH/scripts/lib/deploy-common.sh"
detect_compose

export APP_VERSION="$IMAGE_TAG"

sync_images() {
    if [ "$LOCAL_MODE" = "true" ]; then
        log "Building locally: $*"
        compose build "$@"
    else
        log "Pulling: $*"
        compose pull "$@"
    fi
}

is_sortable_version() {
    [[ "$1" =~ ^[0-9]+([.][0-9]+){1,3}([-+][0-9A-Za-z.-]+)?$ ]]
}

run_one_off() {
    local service="$1"
    docker rm -f "$service" >/dev/null 2>&1 || true
    compose up --force-recreate --no-deps \
        --exit-code-from "$service" "$service"
    compose rm -f -s "$service" >/dev/null 2>&1 || true
}

log "Ensuring database and Redis are up"
compose up -d postgresql redis

CURRENT_COLOR="$(current_color)"
NEXT_COLOR="$(other_color "$CURRENT_COLOR")"

FIRST_INSTALL=false
if [ "$(docker inspect -f '{{.State.Running}}' \
    "backend-api-${CURRENT_COLOR}" 2>/dev/null)" != "true" ]; then
    FIRST_INSTALL=true
    DEPLOY_COLOR="$CURRENT_COLOR"
    log "No running ${CURRENT_COLOR} API; deploying directly to ${DEPLOY_COLOR}"
else
    DEPLOY_COLOR="$NEXT_COLOR"
    log "Current color: $CURRENT_COLOR; deploying to: $DEPLOY_COLOR"
fi

if [ "$LOCAL_MODE" != "true" ] && [ "$FIRST_INSTALL" != "true" ]; then
    CURRENT_VERSION="$(color_version "$CURRENT_COLOR")"
    if [ -n "$CURRENT_VERSION" ]; then
        if [ "$CURRENT_VERSION" = "$IMAGE_TAG" ]; then
            log "SKIP: active version already equals target $IMAGE_TAG"
            exit 0
        fi
        if is_sortable_version "$CURRENT_VERSION" \
            && is_sortable_version "$IMAGE_TAG"; then
            NEWER="$(printf '%s\n%s\n' "$CURRENT_VERSION" "$IMAGE_TAG" \
                | sort -V | tail -1)"
            if [ "$NEWER" != "$IMAGE_TAG" ]; then
                log "SKIP: active version $CURRENT_VERSION >= target $IMAGE_TAG"
                exit 0
            fi
        fi
    fi
fi

if [ "$LOCAL_MODE" = "true" ]; then
    sync_images "backend-api-${DEPLOY_COLOR}" "frontend-${DEPLOY_COLOR}"
else
    sync_images \
        backend-init \
        backend-runtime-init \
        "backend-api-${DEPLOY_COLOR}" \
        "frontend-${DEPLOY_COLOR}"
fi

log "Running DevMind schema initialization"
run_one_off backend-init

if [ "$FIRST_INSTALL" != "true" ]; then
    log "Migrations must be expand/contract-safe during blue/green deploys."
fi

log "Running DevMind runtime initialization"
run_one_off backend-runtime-init

log "Starting backend-api-${DEPLOY_COLOR} and frontend-${DEPLOY_COLOR}"
compose --profile "$DEPLOY_COLOR" up -d \
    "backend-api-${DEPLOY_COLOR}" "frontend-${DEPLOY_COLOR}"

log "Waiting for backend-api-${DEPLOY_COLOR} to become healthy"
if ! wait_for_healthy_container "backend-api-${DEPLOY_COLOR}"; then
    compose --profile "$DEPLOY_COLOR" stop \
        "backend-api-${DEPLOY_COLOR}" "frontend-${DEPLOY_COLOR}"
    die "backend-api-${DEPLOY_COLOR} never became healthy."
fi

log "Waiting for frontend-${DEPLOY_COLOR} to become healthy"
if ! wait_for_healthy_container "frontend-${DEPLOY_COLOR}"; then
    compose --profile "$DEPLOY_COLOR" stop \
        "backend-api-${DEPLOY_COLOR}" "frontend-${DEPLOY_COLOR}"
    die "frontend-${DEPLOY_COLOR} never became healthy."
fi

record_active_color() {
    echo "$DEPLOY_COLOR" > "$DEPLOY_PATH/.active_color"
}

compose up -d nginx

if [ "$FIRST_INSTALL" = "true" ]; then
    set_traffic_color "$DEPLOY_COLOR"
    record_active_color
    log "First install is serving ${DEPLOY_COLOR}"
    docker rm -f backend-api frontend >/dev/null 2>&1 || true
else
    switch_traffic "$CURRENT_COLOR" "$DEPLOY_COLOR"
    record_active_color
    log "Observing ${DEPLOY_COLOR} for ${POST_SWITCH_OBSERVE_SECONDS}s"
    sleep "$POST_SWITCH_OBSERVE_SECONDS"
    log "Stopping previous color: ${CURRENT_COLOR}"
    compose --profile "$CURRENT_COLOR" stop \
        "backend-api-${CURRENT_COLOR}" "frontend-${CURRENT_COLOR}"
    compose --profile "$CURRENT_COLOR" rm -f \
        "backend-api-${CURRENT_COLOR}" "frontend-${CURRENT_COLOR}"
fi

log "Rolling backend-worker and backend-scheduler to ${IMAGE_TAG}"
if [ "$LOCAL_MODE" = "true" ]; then
    compose build "backend-api-${DEPLOY_COLOR}"
else
    sync_images backend-worker backend-scheduler
fi
compose up -d backend-worker backend-scheduler
write_color_version "$DEPLOY_COLOR" "$IMAGE_TAG"

prune_old_image_tags() {
    local repo="$1"
    docker images "$repo" --format "{{.Tag}}" \
        | grep -vE '^(latest|<none>)$' | sort -rV | tail -n +4 \
        | while read -r tag; do
            docker rmi "${repo}:${tag}" >/dev/null 2>&1 \
                && log "Pruned old image: ${repo}:${tag}"
        done || true
}

if [ "$LOCAL_MODE" != "true" ] \
    && [ "$DEPLOY_PRUNE_OLD_IMAGES" = "true" ]; then
    prune_old_image_tags "$BACKEND_IMAGE_REPO"
    prune_old_image_tags "$FRONTEND_IMAGE_REPO"
    docker image prune -f >/dev/null
fi

log "Deploy complete: ${GIT_REF} as ${IMAGE_TAG}; active color: ${DEPLOY_COLOR}"
