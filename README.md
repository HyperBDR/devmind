# DevMind

English | [中文](README.zh-CN.md)

AI-powered acceleration platform for internal enterprise use, enabling AI-driven R&D project management, financial data analysis, and other intelligent workflows.

## Agentcore submodules

Common modules (e.g. LLM tracking, task execution tracking, notifier) are maintained as separate repositories and included here as **git submodules** under `devmind/agentcore/`.

### How agentcore is installed

- **Production (Docker)**  
  Dependencies are declared in `pyproject.toml` and point to GitHub. When you build the image with `docker-compose up -d` (or `docker-compose build`), the Dockerfile installs all dependencies from `pyproject.toml`; agentcore packages are installed from GitHub and no local path is used.

- **Development (Docker)**  
  Use `docker-compose -f docker-compose.dev.yml` so the image is built with `DEV_MODE=1`. The Dockerfile then does one extra step after the main dependency install: for each directory under `devmind/agentcore/*/` that has a `pyproject.toml`, it runs `pip install -e .` there. That overlays the GitHub-installed agentcore with your **local** agentcore code in editable mode, so you can change code under `devmind/agentcore/` and debug without rebuilding the image (especially when combined with volume mounts in `docker-compose.dev.yml`).

- **Local / non-Docker**  
  After cloning, run `git submodule update --init --recursive`, then install the project. To develop agentcore locally, install each submodule in editable mode (see below).

### After cloning the repo: fetch submodules first

**If you just cloned the repo, you must initialize and fetch submodules** so that agentcore packages are available; otherwise Python imports and Django apps will fail.

```bash
git submodule update --init --recursive
```

### Installing agentcore packages in editable mode (local / non-Docker dev)

From the repository root (the `devmind/` directory that contains `pyproject.toml`):

```bash
for d in devmind/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && pip install -e "$d"
done
```

With `uv`:

```bash
for d in devmind/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && uv pip install -e "$d"
done
```

### Submodule mapping and usage

| Submodule            | Replaces (legacy) | Django app (INSTALLED_APPS)          | Import / URL mount                    |
|----------------------|-------------------|--------------------------------------|----------------------------------------|
| `agentcore-metering` | llm_tracker       | `agentcore_metering.adapters.django` | `agentcore_metering.*`, `api/v1/admin/` |
| `agentcore-task`     | —                 | `agentcore_task.adapters.django`     | `agentcore_task.*`, `api/v1/tasks/`    |

## Celery: auto-loading app tasks and entrypoint behavior

### How task code is loaded

- In `core/celery.py`, the Celery app calls `app.autodiscover_tasks()` with no arguments. Celery then looks for a `tasks.py` module in every app listed in Django’s `INSTALLED_APPS` and imports it, so all `@app.task` / `@shared_task` functions from those apps are registered.
- Any Django app (including agentcore packages) that is in `INSTALLED_APPS` and provides a `tasks.py` is automatically discovered; no extra configuration is required.

### How periodic tasks are registered

- Periodic (cron-like) tasks are not discovered by Celery alone; they are registered into **django_celery_beat** so the beat scheduler can run them.
- The management command `python manage.py register_periodic_tasks` discovers, for each app in `INSTALLED_APPS`, a `periodic_tasks` module and, if it defines a `register_periodic_tasks()` function, calls it. Each app uses the project’s `core.periodic_registry` to declare cron entries; the command then writes these entries into the django_celery_beat database tables (idempotent).

### How this runs in `docker/entrypoint.sh`

- The entrypoint sets `PYTHONPATH=/opt/devmind` and `DJANGO_SETTINGS_MODULE=core.settings`, so that when Celery is started with `-A core`, it loads `core.celery` and Django settings (including `INSTALLED_APPS`) are available.
- **`celery` (worker)** and **`celery-beat`**: When the container runs `celery -A core worker` or `celery -A core beat`, importing `core.celery` runs `autodiscover_tasks()`, so all app `tasks.py` modules are loaded and tasks are visible to the worker and to beat. Beat uses `DatabaseScheduler`, so it reads the schedule from the database.
- **`gunicorn`** and **`development`**: After `wait_for_db` and `run_migrations`, the entrypoint runs `python manage.py register_periodic_tasks` (or true). That populates django_celery_beat with the periodic entries from every app’s `periodic_tasks.register_periodic_tasks()`. In a typical multi-container setup, the web container (gunicorn) runs migrations and `register_periodic_tasks` once; the celery and celery-beat containers then start and use the same database, so they see the registered tasks and schedule without running the command again.

## Development Environment

### Requirements

- Docker & Docker Compose
- Git

### Setup

0. **If you cloned the repo:** run `git submodule update --init --recursive` (see [Agentcore submodules](#after-cloning-the-repo-fetch-submodules-first) above).

1. Copy environment configuration file:

```bash
cp env.sample .env.dev
```

2. Configure environment variables:

Edit `.env.dev` file and set necessary configurations (database, AI services, etc.)

3. Start services:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

4. Access services:

- Web UI: http://localhost:8000
- API Documentation: http://localhost:8000/swagger/
- Admin Panel: http://localhost:8000/admin/
- Celery Monitor: http://localhost:5555

## Production Environment

### Requirements

- Docker & Docker Compose
- Server resources (recommended: at least 4 CPU cores, 8GB RAM)

### Deployment

1. Copy environment configuration file:

```bash
cp env.sample .env
```

2. Configure production environment variables:

Edit `.env` file and configure:
- `SECRET_KEY`: Django secret key (must be changed in production)
- `DJANGO_DEBUG=false`: Disable debug mode
- `ALLOWED_HOSTS`: Allowed domain names
- `CSRF_TRUSTED_ORIGINS`: Trusted domain names
- Database configuration (PostgreSQL - recommended, or MySQL/MariaDB for backward compatibility)
- AI service configuration (OpenAI/Azure OpenAI)
- Other necessary production configurations

3. Start services:

```bash
docker-compose up -d
```

4. Check service status:

```bash
docker-compose ps
```

5. View logs:

```bash
docker-compose logs -f
```

### Default Ports

- HTTP: 10080
- HTTPS: 10443

Port configuration can be modified via `NGINX_HTTP_PORT` and `NGINX_HTTPS_PORT` in the `.env` file.
