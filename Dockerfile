# syntax=docker/dockerfile:1.6

# -----------------------------------------------------------------------------
# Backend builder image
# -----------------------------------------------------------------------------

FROM python:3.12-slim-bookworm AS backend-builder

# Build argument to control mirror usage
ARG USE_MIRROR=false

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Setup mirrors based on build argument before installing packages.
RUN set -eux; \
    if [ "$USE_MIRROR" = "true" ]; then \
        printf '%s\n' \
            'Types: deb' \
            'URIs: https://mirrors.aliyun.com/debian' \
            'Suites: bookworm bookworm-updates bookworm-backports' \
            'Components: main contrib non-free non-free-firmware' \
            'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
            '' \
            'Types: deb' \
            'URIs: https://mirrors.aliyun.com/debian-security' \
            'Suites: bookworm-security' \
            'Components: main contrib non-free non-free-firmware' \
            'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
            > /etc/apt/sources.list.d/debian.sources; \
        echo "Chinese Debian mirrors configured"; \
    else \
        echo "Using default Debian sources"; \
    fi; \
    apt-get update

# Install build-only system dependencies.
# libmagic is for python-magic file type detection.
# gettext is for Django i18n commands.
RUN apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    curl \
    git \
    default-libmysqlclient-dev \
    libpq-dev \
    libmagic-dev \
    libxml2-dev \
    libxslt1-dev \
    gettext \
    pkg-config \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Install uv using pip with mirror selection.
RUN set -eux; \
    if [ "$USE_MIRROR" = "true" ]; then \
        echo "Installing uv with Chinese PyPI mirror"; \
        pip install --retries 5 --timeout 120 --progress-bar off \
            --index-url https://mirrors.aliyun.com/pypi/simple \
            --trusted-host mirrors.aliyun.com uv; \
    else \
        echo "Installing uv with default PyPI"; \
        pip install --retries 5 --timeout 120 --progress-bar off uv; \
    fi; \
    python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

WORKDIR /opt/backend

# Copy project files.
COPY backend /opt/backend
COPY pyproject.toml /opt/backend/

# Install project dependencies with mirror selection.
RUN set -eux; \
    if [ "$USE_MIRROR" = "true" ]; then \
        echo "Using Chinese PyPI mirror for dependencies"; \
        uv pip compile pyproject.toml -o requirements.txt \
            --index-url https://mirrors.aliyun.com/pypi/simple; \
        uv pip install --python /opt/venv/bin/python -r requirements.txt \
            --index-url https://mirrors.aliyun.com/pypi/simple; \
    else \
        echo "Using default PyPI for dependencies"; \
        uv pip compile pyproject.toml -o requirements.txt; \
        uv pip install --python /opt/venv/bin/python -r requirements.txt; \
    fi

# Dev mode overlays local agentcore packages after unified dependencies.
# Without DEV_MODE=1, agentcore packages come from GitHub in pyproject.toml.
ARG DEV_MODE=0
RUN set -eux; \
    if [ "$DEV_MODE" = "1" ]; then \
        for d in agentcore/*/; do \
            if [ -f "${d}pyproject.toml" ]; then \
                echo "Dev mode: pip install -e $d"; \
                (cd "$d" && uv pip install \
                    --python /opt/venv/bin/python -e .); \
            fi; \
        done; \
    fi

# Compile Django message catalogs (.po -> .mo) so runtime gettext works.
RUN python manage.py compilemessages -l zh_Hans -l en

RUN rm -rf /root/.cache /tmp/* \
    && find /opt/venv -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find /opt/backend -type d -name __pycache__ -prune -exec rm -rf {} +

# -----------------------------------------------------------------------------
# Backend runtime image
# -----------------------------------------------------------------------------

FROM python:3.12-slim-bookworm AS backend

ARG USE_MIRROR=false

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv

RUN set -eux; \
    if [ "$USE_MIRROR" = "true" ]; then \
        printf '%s\n' \
            'Types: deb' \
            'URIs: https://mirrors.aliyun.com/debian' \
            'Suites: bookworm bookworm-updates bookworm-backports' \
            'Components: main contrib non-free non-free-firmware' \
            'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
            '' \
            'Types: deb' \
            'URIs: https://mirrors.aliyun.com/debian-security' \
            'Suites: bookworm-security' \
            'Components: main contrib non-free non-free-firmware' \
            'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
            > /etc/apt/sources.list.d/debian.sources; \
        echo "Chinese Debian mirrors configured"; \
    else \
        echo "Using default Debian sources"; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

WORKDIR /opt/backend

COPY --from=backend-builder /opt/venv /opt/venv
COPY --from=backend-builder /opt/backend /opt/backend

# Create necessary directories.
RUN mkdir -p /var/log/gunicorn /var/log/celery /var/cache/backend

# Copy entrypoint script.
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# -----------------------------------------------------------------------------
# Frontend image
# -----------------------------------------------------------------------------

FROM node:22-alpine AS frontend-builder

WORKDIR /app

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY frontend/package*.json ./

RUN npm ci --only=production=false

COPY frontend ./

RUN npm run build

FROM nginx:alpine AS frontend

COPY --from=frontend-builder /app/dist /usr/share/nginx/html
COPY frontend/docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
