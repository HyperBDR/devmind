# DevMind

AI-powered acceleration platform for internal enterprise use, enabling AI-driven R&D project management, financial data analysis, and other intelligent workflows.

## Agentcore submodules

Common modules (e.g. LLM tracking, config, task manager, notifier) are maintained as separate repositories and included here as **git submodules** under `devmind/agentcore/`. The project uses them via editable installs and does not keep a local compatibility layer.

### After cloning the repo

Initialize and fetch submodules:

```bash
git submodule update --init --recursive
```

### Installing agentcore packages (local and CI)

Each submodule under `devmind/agentcore/` is a pip-installable package. Install them in editable mode so the project can import `agentcore_xxx`:

```bash
# From the repository root (devmind/)
for d in devmind/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && pip install -e "$d"
done
```

If using `uv`:

```bash
for d in devmind/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && uv pip install -e "$d"
done
```

Docker builds run the same logic in the Dockerfile after installing main dependencies.

### Submodule mapping and usage

| Submodule               | Replaces (legacy) | Django app (INSTALLED_APPS)              | Import / URL mount |
|-------------------------|-------------------|------------------------------------------|---------------------|
| `agentcore-tracking`    | llm_tracker       | `agentcore_tracking.adapters.django`     | `agentcore_tracking.*`, `api/v1/admin/` |

Future submodules (e.g. agentcore-config, agentcore-task-tracker, agentcore-notifier) follow the same pattern and are installed the same way.

## Development Environment

### Requirements

- Docker & Docker Compose
- Git

### Setup

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
