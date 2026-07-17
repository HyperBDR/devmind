#!/bin/bash
# Day-2 operations for an installed DevMind blue/green stack.
set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-$(pwd)}"
cd "$DEPLOY_PATH"

log() { echo -e "\033[1;36m[devmindctl]\033[0m $*"; }
die() { echo -e "\033[1;31m[devmindctl] ERROR:\033[0m $*" >&2; exit 1; }

acquire_deploy_lock() {
    local lock_file="/tmp/devmind-install.lock"
    local max_wait=300
    local waited=0
    while ! (set -o noclobber; echo "$$ $(date)" > "$lock_file") 2>/dev/null; do
        if [ "$waited" -ge "$max_wait" ]; then
            log "Lock $lock_file still held after ${max_wait}s; taking it over"
            echo "$$ $(date)" > "$lock_file"
            break
        fi
        log "A deploy or ops command is running, waiting... (${waited}s)"
        sleep 5
        waited=$((waited + 5))
    done
    trap 'rm -f "'"$lock_file"'"' EXIT
}

[ -f "$DEPLOY_PATH/scripts/lib/deploy-common.sh" ] \
    || die "scripts/lib/deploy-common.sh not found; run install.sh first."

# shellcheck source=./lib/deploy-common.sh
source "$DEPLOY_PATH/scripts/lib/deploy-common.sh"
detect_compose

cmd_status() {
    local active status
    active="$(current_color)"
    log "Active color: ${active}"
    log "Blue version: $(color_version blue || true)"
    log "Green version: $(color_version green || true)"
    echo
    compose ps \
        "backend-api-${active}" "frontend-${active}" \
        backend-worker backend-scheduler nginx \
        2>/dev/null || true
    echo
    status="$(
        docker inspect \
            --format='{{if .State.Health}}{{.State.Health.Status}}{{end}}' \
            "backend-api-${active}" 2>/dev/null || true
    )"
    if [ "$status" = "healthy" ]; then
        log "backend-api-${active}: healthy"
    else
        log "backend-api-${active}: ${status:-not running}"
    fi
}

cmd_restart_workers() {
    acquire_deploy_lock
    log "Restarting backend-worker and backend-scheduler"
    compose restart backend-worker backend-scheduler
    log "Done"
}

cmd_rollback() {
    acquire_deploy_lock
    local active target target_version
    active="$(current_color)"
    target="$(other_color "$active")"
    target_version="$(color_version "$target")"
    [ -n "$target_version" ] \
        || die "No recorded version for ${target}; rollback is unavailable."

    export APP_VERSION="$target_version"
    log "Rolling back from ${active} to ${target} (${target_version})"

    compose --profile "$target" up -d \
        "backend-api-${target}" "frontend-${target}"

    log "Waiting for backend-api-${target} to become healthy"
    if ! wait_for_healthy_container "backend-api-${target}"; then
        compose --profile "$target" stop \
            "backend-api-${target}" "frontend-${target}"
        die "backend-api-${target} never became healthy; rollback aborted."
    fi

    log "Waiting for frontend-${target} to become healthy"
    if ! wait_for_healthy_container "frontend-${target}"; then
        compose --profile "$target" stop \
            "backend-api-${target}" "frontend-${target}"
        die "frontend-${target} never became healthy; rollback aborted."
    fi

    compose up -d nginx
    switch_traffic "$active" "$target"
    echo "$target" > "$DEPLOY_PATH/.active_color"

    log "Rolling backend-worker and backend-scheduler back to ${target_version}"
    compose up -d backend-worker backend-scheduler

    log "Rolled back. Active color is now ${target}."
    log "${active} is left running or stopped as-is for inspection."
}

case "${1:-}" in
    status)
        cmd_status
        ;;
    restart-workers)
        cmd_restart_workers
        ;;
    rollback)
        cmd_rollback
        ;;
    *)
        die "Usage: $0 {status|restart-workers|rollback}"
        ;;
esac
