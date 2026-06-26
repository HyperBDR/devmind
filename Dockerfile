# Use official Python 3.12 on Ubuntu 24.04 LTS
FROM ubuntu:24.04 AS backend

# Build argument to control mirror usage
ARG USE_MIRROR=false

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install ca-certificates first to avoid SSL certificate issues
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates

# Setup mirrors based on build argument (before installing packages)
RUN set -eux; \
    if [ "$USE_MIRROR" = "true" ]; then \
        echo "Setting up Chinese mirrors for Ubuntu 24.04 LTS..."; \
        arch="$(dpkg --print-architecture)"; \
        mirror_path="ubuntu"; \
        if [ "$arch" != "amd64" ]; then \
            mirror_path="ubuntu-ports"; \
        fi; \
        if [ -f /etc/apt/sources.list ]; then \
            cp /etc/apt/sources.list /etc/apt/sources.list.backup; \
        fi; \
        if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then \
            cp /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.backup; \
            rm -f /etc/apt/sources.list.d/ubuntu.sources; \
        fi; \
        echo "deb https://mirrors.aliyun.com/${mirror_path}/ noble main restricted universe multiverse" > /etc/apt/sources.list; \
        echo "deb https://mirrors.aliyun.com/${mirror_path}/ noble-updates main restricted universe multiverse" >> /etc/apt/sources.list; \
        echo "deb https://mirrors.aliyun.com/${mirror_path}/ noble-backports main restricted universe multiverse" >> /etc/apt/sources.list; \
        echo "deb https://mirrors.aliyun.com/${mirror_path}/ noble-security main restricted universe multiverse" >> /etc/apt/sources.list; \
        echo "✓ Chinese mirrors configured for Ubuntu 24.04 LTS (Noble Numbat)"; \
        echo "Architecture: ${arch}; mirror path: ${mirror_path}"; \
        echo "Current sources.list content:"; \
        cat /etc/apt/sources.list; \
    else \
        echo "Using default Ubuntu sources"; \
    fi; \
    apt-get update

# Install Python 3.12, pip and system dependencies in one step
# libmagic is for python-magic which is a library for file type detection
# gettext is for Django i18n (makemessages, compilemessages)
# postgresql-client is for PostgreSQL database support
RUN apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-dev \
    python3-pip \
    build-essential \
    git \
    curl \
    default-libmysqlclient-dev \
    libpq-dev \
    postgresql-client \
    pkg-config \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libmagic1 \
    libmagic-dev \
    gettext \
    procps \
    htop \
    net-tools \
    iputils-ping \
    dnsutils \
    mariadb-client \
    # Note: MySQL/MariaDB packages are kept for backward compatibility
    # PostgreSQL is the recommended database (postgresql-client, libpq-dev)
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Disable externally-managed-environment restriction for container environment
RUN rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED

# Install uv using pip with mirror selection
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
    echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc; \
    export PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /opt/backend

# Copy project files
COPY backend /opt/backend
COPY pyproject.toml /opt/backend/

# Install project dependencies with mirror selection
RUN set -eux; \
    export PATH="/root/.local/bin:$PATH"; \
    if [ "$USE_MIRROR" = "true" ]; then \
        echo "Using Chinese PyPI mirror for dependencies"; \
        uv pip compile pyproject.toml -o requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple; \
        uv pip install --system -r requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple; \
    else \
        echo "Using default PyPI for dependencies"; \
        uv pip compile pyproject.toml -o requirements.txt; \
        uv pip install --system -r requirements.txt; \
    fi

# Dev mode: after unified deps, overlay agentcore from image copy in editable mode.
# Without DEV_MODE=1, agentcore-task/agentcore-metering come from GitHub only (see
# pyproject.toml). Use DEV_MODE=1 when building to pick up local agentcore fixes
# (e.g. django __getattr__ recursion fix) without publishing to GitHub first.
# COPY backend /opt/backend puts agentcore at /opt/backend/agentcore/, so loop uses agentcore/*/
ARG DEV_MODE=0
RUN set -eux; \
    if [ "$DEV_MODE" = "1" ]; then \
        export PATH="/root/.local/bin:$PATH"; \
        for d in agentcore/*/; do \
            if [ -f "${d}pyproject.toml" ]; then \
                echo "Dev mode: pip install -e $d"; \
                (cd "$d" && uv pip install --system -e .); \
            fi; \
        done; \
    fi

# Compile Django message catalogs (.po -> .mo) so runtime gettext works
RUN python manage.py compilemessages -l zh_Hans -l en

# Create necessary directories
RUN mkdir -p /var/log/gunicorn /var/log/celery /var/cache/backend

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set default command
ENTRYPOINT ["/entrypoint.sh"]

# -----------------------------------------------------------------------------
# Frontend image
# -----------------------------------------------------------------------------

FROM node:22-alpine AS frontend-builder

WORKDIR /app

ARG VITE_API_BASE_URL
ARG VITE_APP_VERSION
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_APP_VERSION=${VITE_APP_VERSION}

COPY frontend/package*.json ./

RUN npm ci --only=production=false

COPY frontend ./

RUN npm run build

FROM nginx:alpine AS frontend

COPY --from=frontend-builder /app/dist /usr/share/nginx/html
COPY frontend/docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
