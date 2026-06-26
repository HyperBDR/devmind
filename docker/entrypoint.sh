#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# Project Entrypoint Script
# -----------------------------------------------------------------------------
# This script manages database health checks, migrations, static collection,
# and process startup for Django, Celery, Gunicorn, etc.
# -----------------------------------------------------------------------------

# --- Change to project directory ---
cd /opt/backend || { echo "Error: Cannot change to /opt/backend directory"; exit 1; }

# --- Global Variables ---
export PYTHONPATH=/opt/backend
export DJANGO_SETTINGS_MODULE=core.settings

LOG_BASE_DIR="/var/log/gunicorn"
ACCESS_LOG="${LOG_BASE_DIR}/gunicorn_access.log"
ERROR_LOG="${LOG_BASE_DIR}/gunicorn_error.log"
CELERY_LOG="/var/log/celery/celery.log"

WORKERS=${WORKERS:-1}
THREADS=${THREADS:-1}
REDIS_URL=${REDIS_URL:-redis://redis:6379/0}
REDIS_HEALTHCHECK_URL=${REDIS_HEALTHCHECK_URL:-${CELERY_BROKER_URL:-$REDIS_URL}}
DB_ENGINE=${DB_ENGINE:-sqlite}
RUN_STARTUP_MAINTENANCE=${RUN_STARTUP_MAINTENANCE:-false}

# --- Ensure log directories exist ---
mkdir -p $LOG_BASE_DIR /var/log/celery
chmod -R 755 $LOG_BASE_DIR /var/log/celery


# --- Logging Helper ---
log() { echo -e "\033[1;36m[entrypoint]\033[0m $*"; }

# --- Database Health Check ---
wait_for_db() {
    log "Waiting for database engine: $DB_ENGINE"
    case "$DB_ENGINE" in
        mysql)
            HOST=${MYSQL_HOST:-localhost}
            PORT=${MYSQL_PORT:-3306}
            log "Waiting for MySQL at $HOST:$PORT..."
            until python - <<PY
import os
import sys

import pymysql

try:
    connection = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "app"),
        connect_timeout=2,
        read_timeout=2,
        write_timeout=2,
    )
    connection.close()
except Exception:
    sys.exit(1)
PY
            do
                sleep 2
            done
            log "MySQL is ready!"
            ;;
        postgresql|postgres)
            # In Docker Compose, use service name 'postgresql' as default host.
            # For local development, use 'localhost'.
            HOST=${POSTGRES_HOST:-postgresql}
            PORT=${POSTGRES_PORT:-5432}
            log "Waiting for PostgreSQL at $HOST:$PORT..."
            until python - <<PY
import os
import sys

import psycopg2

try:
    connection = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "postgresql"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        dbname=os.environ.get("POSTGRES_DB", "postgres"),
        connect_timeout=2,
    )
    connection.close()
except Exception:
    sys.exit(1)
PY
            do
                sleep 2
            done
            log "PostgreSQL is ready!"
            ;;
        *)
            log "Using SQLite (no health check required)."
            ;;
    esac
}

wait_for_redis() {
    log "Waiting for Redis..."
    until python - <<PY
import os
import redis

client = redis.from_url(
    os.environ.get("REDIS_HEALTHCHECK_URL", "redis://redis:6379/0"),
    socket_connect_timeout=2,
    socket_timeout=2,
)
client.ping()
PY
    do
        sleep 2
    done
    log "Redis is ready!"
}

# --- Django Management Tasks ---
run_startup_maintenance() {
    log "Running backend initialization..."
    python manage.py init_backend
}

run_schema_initialization() {
    log "Running backend schema initialization..."
    python manage.py init_backend --phase schema
}

run_runtime_initialization() {
    log "Running backend runtime initialization..."
    python manage.py init_backend --phase runtime
}

# --- Process Starters ---
start_gunicorn() {
    log "Starting Gunicorn..."
    exec gunicorn core.wsgi:application \
        --name backend \
        --bind 0.0.0.0:8000 \
        --workers $WORKERS \
        --threads $THREADS \
        --worker-class gthread \
        --log-level info \
        --access-logfile $ACCESS_LOG \
        --error-logfile $ERROR_LOG
}

start_celery_worker() {
    log "Starting Celery worker..."

    # Get CPU count for default concurrency
    # For I/O-bound tasks, we can use higher concurrency
    CPU_COUNT=$(nproc 2>/dev/null || echo 4)

    # Default concurrency: use CPU count for I/O-bound tasks
    # Can be overridden by CELERY_CONCURRENCY environment variable
    DEFAULT_CONCURRENCY=${CELERY_CONCURRENCY:-$CPU_COUNT}

    log "Celery worker concurrency: $DEFAULT_CONCURRENCY (CPUs: $CPU_COUNT)"
    log "Graceful shutdown enabled: worker will wait for running tasks to complete (up to stop_grace_period)"

    # Celery worker will gracefully shutdown when receiving SIGTERM:
    # - Stops accepting new tasks
    # - Waits for currently running tasks to complete
    # - Docker stop_grace_period (600s) allows time for tasks to finish
    # - CELERY_TASK_ACKS_LATE=True ensures tasks are only acknowledged after completion
    exec celery -A core.celery:app worker \
        --loglevel=${CELERY_LOG_LEVEL:-INFO} \
        --concurrency=$DEFAULT_CONCURRENCY \
        --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD:-1000} \
        --max-memory-per-child=${CELERY_MAX_MEMORY_PER_CHILD:-256000} \
        --logfile=/var/log/celery/worker.log
}

start_celery_beat() {
    log "Starting Celery beat with DatabaseScheduler..."
    exec celery -A core.celery:app beat \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \
        --loglevel=${CELERY_LOG_LEVEL:-INFO} \
        --logfile=/var/log/celery/beat.log
}

start_flower() {
    log "Starting Flower..."
    exec celery -A core.celery:app flower \
        --port=${FLOWER_PORT:-5555} \
        --address=0.0.0.0 \
        --broker="$REDIS_URL" \
        --loglevel=${CELERY_LOG_LEVEL:-INFO} \
        --logfile=/var/log/celery/flower.log
}

start_development() {
    log "Starting Django development server (runserver)..."
    exec python manage.py runserver 0.0.0.0:8000
}

# --- Main Entrypoint ---
case "$1" in
    init)
        wait_for_db
        run_startup_maintenance
        ;;
    init-schema)
        wait_for_db
        run_schema_initialization
        ;;
    init-runtime)
        wait_for_db
        run_runtime_initialization
        ;;
    create-superuser)
        wait_for_db
        python manage.py create_default_superuser
        ;;
    gunicorn)
        wait_for_db
        if [ "$RUN_STARTUP_MAINTENANCE" = "true" ]; then
            log "RUN_STARTUP_MAINTENANCE=true; running maintenance before Gunicorn..."
            run_startup_maintenance
        else
            log "Skipping startup maintenance before Gunicorn."
        fi
        start_gunicorn
        ;;
    celery)
        wait_for_db
        wait_for_redis
        start_celery_worker
        ;;
    celery-beat)
        wait_for_db
        wait_for_redis
        start_celery_beat
        ;;
    flower)
        wait_for_redis
        start_flower
        ;;
    development)
        wait_for_db
        if [ "$RUN_STARTUP_MAINTENANCE" = "true" ]; then
            log "RUN_STARTUP_MAINTENANCE=true; running maintenance before runserver..."
            run_startup_maintenance
        else
            log "Skipping startup maintenance before runserver."
        fi
        start_development
        ;;
    *)
        exec "$@"
        ;;
esac
