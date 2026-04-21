# DevMind

[English](README.md) | [中文](README.zh-CN.md)

AI-powered acceleration platform for internal enterprise use, enabling AI-driven R&D project management, financial data analysis, and other intelligent workflows.

## Architecture Overview

```
devmind/
├── backend/               # Django REST API
│   ├── core/              # Project config (settings/, urls.py, celery.py, periodic_registry.py)
│   ├── accounts/          # Auth, Profile, Role, Permission
│   ├── cloud_billing/     # Cloud billing (AWS / Azure / Alibaba / Huawei / Tencent)
│   ├── data_collector/    # Raw data collection from JIRA, Feishu, etc.
│   ├── ai_pricehub/       # AI model price comparison
│   ├── app_config/        # Global config (Feature Flags)
│   └── agentcore/         # Git submodules
│       ├── agentcore-metering/   # LLM usage tracking  → /api/v1/admin/
│       ├── agentcore-task/       # Unified task mgmt  → /api/v1/tasks/
│       └── agentcore-notifier/   # Feishu notifier    → /api/v1/admin/notifications/
└── frontend/              # Vue 3 (Vite + Pinia + Tailwind + vue-i18n)
```

**Key architectural notes**:
- All data is stored in UTC; frontend converts to user's local timezone
- Each Django app is self-contained (owns its own models, views, serializers, services, migrations, tests)
- Periodic tasks are declared in `periodic_tasks.register_periodic_tasks()` and written to django_celery_beat; existing records are never overwritten

## Quick Start

### 1. Fetch submodules (required after cloning)

```bash
git submodule update --init --recursive
```

### 2. Configure and start (Docker dev)

```bash
cp env.sample .env.dev
# Edit .env.dev — configure database, AI services, etc.
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Access services

| Service | URL |
|---|---|
| Web UI | http://localhost:8000 |
| API Docs | http://localhost:8000/swagger/ |
| Admin Panel | http://localhost:8000/admin/ |
| Celery Monitor | http://localhost:5555 |

### 4. Common Commands

```bash
# Backend
pytest                                    # Run all tests
pytest path/to/test.py                    # Single test file
black --check backend/                    # Check formatting
isort --check backend/                   # Check import order

# Django management
python backend/manage.py migrate
python backend/manage.py register_periodic_tasks   # Register periodic tasks
python backend/manage.py createsuperuser

# Frontend
cd frontend && npm install
npm run dev          # Dev server
npm run build        # Production build
npm run lint
npm run test:e2e     # Playwright E2E
```

## Agentcore Submodules in Detail

Common modules (LLM tracking, task management, notifier) are maintained as separate repositories and included as git submodules.

### Installation by Environment

| Environment | Approach |
|---|---|
| Production (Docker) | `pyproject.toml` dependencies point to GitHub; installed automatically during image build |
| Dev (Docker) | `DEV_MODE=1` image additionally runs `pip install -e .` to overlay local agentcore |
| Local / non-Docker | After cloning, manually `pip install -e "$d"` per submodule (see below) |

### Local Editable Install

```bash
for d in backend/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && pip install -e "$d"
done
```

### Submodule Mapping

| Submodule | Django app (INSTALLED_APPS) | URL prefix |
|---|---|---|
| `agentcore-metering` | `agentcore_metering.adapters.django` | `/api/v1/admin/` |
| `agentcore-task` | `agentcore_task.adapters.django` | `/api/v1/tasks/` |
| `agentcore-notifier` | `agentcore_notifier.adapters.django` | `/api/v1/admin/notifications/` |

## Celery: Task Discovery and Periodic Task Registration

### Task Discovery

`core/celery.py` calls `app.autodiscover_tasks()` which automatically loads `tasks.py` from every app in `INSTALLED_APPS`. Any Django app in `INSTALLED_APPS` that provides a `tasks.py` is discovered automatically — no extra configuration needed.

### Periodic Task Registration

Periodic (cron-like) tasks are **not** auto-discovered by Celery alone. They must be written to **django_celery_beat** via `python manage.py register_periodic_tasks`:

1. Iterates over every app in `INSTALLED_APPS` looking for a `periodic_tasks` module
2. If the module defines `register_periodic_tasks()`, it is called
3. Each app declares cron entries using `core.periodic_registry`
4. The registry **only creates missing rows** — existing django_celery_beat records are left untouched

### Entrypoint.sh Execution Order

| Container | Behavior |
|---|---|
| gunicorn / development | `wait_for_db` → `migrate` → `register_periodic_tasks` → start service |
| celery | `wait_for_db` → start worker (`autodiscover_tasks` loads tasks) |
| celery-beat | `wait_for_db` → start beat (`DatabaseScheduler` reads schedule from DB) |

In a typical multi-container setup, the gunicorn container runs `register_periodic_tasks` once; celery and celery-beat share the same database and see the registered tasks without running the command again.

## Design Principles

For decoupling, **each application (app) must manage its own resources**—including database, APIs, and configuration. See [docs/DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md).  
设计原则（中文）：[docs/DESIGN_PRINCIPLES.zh-CN.md](docs/DESIGN_PRINCIPLES.zh-CN.md).

## Production Deployment

```bash
cp env.sample .env
# Edit .env: SECRET_KEY, DJANGO_DEBUG=false, ALLOWED_HOSTS, database, AI services, etc.
APP_VERSION=1.2.3 docker-compose -f docker-compose.yml up -d
```

**Default ports**: HTTP 10080, HTTPS 10443 (configurable via `NGINX_HTTP_PORT` / `NGINX_HTTPS_PORT`)

> The production image version is controlled by `APP_VERSION`. When deploying from a
> Git tag, GitHub Actions strips the leading `v` (for example, `v1.2.3` becomes
> `APP_VERSION=1.2.3`) and runs `docker-compose pull` plus `docker-compose up -d`.
> For manual deployments, set `APP_VERSION` explicitly or Compose will fail with
> `APP_VERSION is required`.

## Frontend

- Vue 3 + Composition API + `<script setup>`
- Vite + Pinia + Vue Router + vue-i18n + Tailwind CSS
- E2E: Playwright

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # Docker: use root `Dockerfile --target frontend`
```

Environment variables: `VITE_API_BASE_URL`, `VITE_APP_TITLE`, `VITE_API_TIMEOUT`
