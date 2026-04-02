# Repository Guidelines

## Project Structure & Module Organization
Core application code lives under `devmind/`. Treat each Django app as self-contained: `accounts/`, `app_config/`, `cloud_billing/`, and `data_collector/` keep their own views, services, migrations, and tests. Shared project wiring is in `devmind/core/` (`settings/`, `urls.py`, `celery.py`, management utilities). Cross-app regression tests live in `devmind/tests/`. Operational files are split between `docker/` for container assets and `docs/` for design and process notes. External `agentcore` packages are checked in as git submodules under `devmind/agentcore/`.

## Build, Test, and Development Commands
Initialize submodules after cloning:
```bash
git submodule update --init --recursive
```
Run the local stack with Docker:
```bash
cp env.sample .env.dev
docker-compose -f docker-compose.dev.yml up -d
```
For non-Docker work, install the package and dev tools:
```bash
pip install -e .[dev]
```
Install local `agentcore` modules in editable mode when needed:
```bash
for d in devmind/agentcore/*/; do [ -f "${d}pyproject.toml" ] && pip install -e "$d"; done
```
Run tests with `pytest`. Use `python devmind/manage.py <command>` for Django management tasks such as migrations or `register_periodic_tasks`.

## Coding Style & Naming Conventions
Use 4-space indentation and follow existing Python conventions: `snake_case` for modules, functions, and variables; `PascalCase` for classes; descriptive app-local service names such as `provider_service.py`. Keep business logic in `services/` or model methods, not in views. The declared formatting and quality tools are `black`, `isort`, `flake8`, and `mypy`; run them before opening a PR.

## Testing Guidelines
Pytest with `pytest-django` is the current test stack. Put app-specific tests in `<app>/tests/` and cross-cutting regressions in `devmind/tests/`. Name files `test_*.py` and test functions `test_<behavior>()`. Mark database-dependent tests with `@pytest.mark.django_db`. Add regression coverage for Celery scheduling, management commands, and billing/provider flows when touching those areas.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects such as `Refine cloud billing provider flows` and `Preserve existing periodic task rows`. Keep commits focused and descriptive. PRs should explain scope, list any config or migration changes, link the related issue, and include screenshots for UI or API doc changes. Note submodule updates explicitly so reviewers verify the referenced `agentcore` revisions.

## Security & Configuration Tips
Do not commit `.env`, secrets, or generated certificates. Start from `env.sample`, keep production values in deployment-managed env files, and review `docker/nginx/certs/` and cloud provider settings carefully before sharing configs.
