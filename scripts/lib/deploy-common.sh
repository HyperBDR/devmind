#!/bin/bash
# Shared helpers for DevMind blue/green deployment scripts.

GRACE_HEALTH_RETRIES="${GRACE_HEALTH_RETRIES:-100}"
GRACE_HEALTH_INTERVAL="${GRACE_HEALTH_INTERVAL:-3}"

detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE=(docker-compose)
    else
        die "Neither 'docker compose' nor 'docker-compose' is available."
    fi
}

compose() {
    "${COMPOSE[@]}" "$@"
}

current_color() {
    cat "$DEPLOY_PATH/.active_color" 2>/dev/null || echo "blue"
}

other_color() {
    [ "$1" = "green" ] && echo "blue" || echo "green"
}

color_version() {
    local color="$1"
    if [ -f "$DEPLOY_PATH/.color_versions" ]; then
        sed -n "s/^${color}=//p" "$DEPLOY_PATH/.color_versions" | tail -1
    fi
}

write_color_version() {
    local color="$1" version="$2"
    local file="$DEPLOY_PATH/.color_versions"
    touch "$file"
    grep -v "^${color}=" "$file" > "${file}.tmp" || true
    printf "%s=%s\n" "$color" "$version" >> "${file}.tmp"
    mv "${file}.tmp" "$file"
}

wait_for_healthy_container() {
    local container="$1"
    local i status
    for i in $(seq 1 "$GRACE_HEALTH_RETRIES"); do
        status=$(
            docker inspect \
                --format='{{if .State.Health}}{{.State.Health.Status}}{{end}}' \
                "$container" 2>/dev/null || true
        )
        if [ "$status" = "healthy" ]; then
            return 0
        fi
        sleep "$GRACE_HEALTH_INTERVAL"
    done
    status=$(
        docker inspect \
            --format='{{if .State.Health}}{{.State.Health.Status}}{{end}}' \
            "$container" 2>/dev/null || true
    )
    [ "$status" = "healthy" ]
}

set_traffic_color() {
    local color="$1"
    local tmp_file upstream_file
    upstream_file="$DEPLOY_PATH/docker/nginx/conf.d/upstream.conf"
    log "Pointing nginx upstreams to ${color}"
    tmp_file="$(mktemp "${upstream_file}.XXXXXX")"
    sed -E \
        -e "s/backend-api-(blue|green)/backend-api-${color}/g" \
        -e "s/frontend-(blue|green)/frontend-${color}/g" \
        "$upstream_file" > "$tmp_file"
    mv "$tmp_file" "$upstream_file"
    docker exec nginx nginx -t
    docker exec nginx nginx -s reload
    log "Traffic now points to ${color}"
}

switch_traffic() {
    local from="$1" to="$2"
    log "Switching nginx upstreams: ${from} -> ${to}"
    set_traffic_color "$to"
}
