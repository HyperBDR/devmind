# DevMind

[English](README.md) | 中文

面向企业内部使用的 AI 加速平台，支持 AI 驱动的研发项目管理、财务数据分析等智能工作流。

## 设计原则

为解耦，**每个应用（app）应自行管理自身资源**，包括数据库、接口、配置等。详见 [docs/DESIGN_PRINCIPLES.zh-CN.md](docs/DESIGN_PRINCIPLES.zh-CN.md)。  
Design principles (English): [docs/DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md).

## Agentcore 子模块

通用模块（如 LLM 追踪、任务执行追踪、通知等）以独立仓库维护，通过 **Git 子模块** 引入到 `devmind/agentcore/` 下。

### Agentcore 的安装方式

- **生产环境（Docker）**  
  依赖写在 `pyproject.toml` 中，并指向 GitHub。使用 `docker-compose up -d`（或先 `docker-compose build`）构建镜像时，Dockerfile 会按 pyproject.toml 安装全部依赖，agentcore 包从 GitHub 安装，不依赖本地路径。

- **开发环境（Docker）**  
  使用 `docker-compose -f docker-compose.dev.yml` 启动时，镜像会以 `DEV_MODE=1` 构建。Dockerfile 在安装完统一依赖后多做一步：对 `devmind/agentcore/*/` 下每个带 `pyproject.toml` 的目录执行 `pip install -e .`，用**本地** agentcore 代码以可编辑方式覆盖 GitHub 版本，便于在 `devmind/agentcore/` 下改代码、调试，而无需重新构建镜像（配合 docker-compose.dev.yml 的 volume 挂载效果更佳）。

- **本地 / 非 Docker**  
  克隆后执行 `git submodule update --init --recursive`，再安装项目。若要在本地开发 agentcore，可对每个子模块做可编辑安装（见下）。

### 克隆仓库后：请先拉取子模块

**若你刚克隆本仓库，必须先初始化并拉取子模块**，否则 agentcore 包不可用，Python 导入和 Django 应用会报错。

```bash
git submodule update --init --recursive
```

### 以可编辑方式安装 agentcore 包（本地 / 非 Docker 开发）

在仓库根目录（即包含 `pyproject.toml` 的 `devmind/` 目录）下执行：

```bash
for d in devmind/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && pip install -e "$d"
done
```

若使用 `uv`：

```bash
for d in devmind/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && uv pip install -e "$d"
done
```

### 子模块与用法对照

| 子模块               | 替代（已废弃） | Django 应用 (INSTALLED_APPS)           | 导入 / URL 挂载                    |
|----------------------|----------------|----------------------------------------|-------------------------------------|
| `agentcore-metering` | llm_tracker    | `agentcore_metering.adapters.django`   | `agentcore_metering.*`、`api/v1/admin/` |
| `agentcore-task`     | —              | `agentcore_task.adapters.django`       | `agentcore_task.*`、`api/v1/tasks/` |

## Celery：自动加载 app 任务与 entrypoint 生效逻辑

### 任务代码如何被加载

- 在 `core/celery.py` 中，Celery 应用会调用 `app.autodiscover_tasks()`（无参数）。Celery 会在 Django `INSTALLED_APPS` 里的每个应用中查找 `tasks.py` 并导入，因此各 app 中通过 `@app.task` / `@shared_task` 定义的任务都会被注册。
- 只要某个 Django 应用（含 agentcore 包）在 `INSTALLED_APPS` 中且提供 `tasks.py`，就会被自动发现，无需额外配置。

### 定时任务如何注册

- 定时（类 cron）任务仅靠 Celery 不会自动发现，需要写入 **django_celery_beat** 后，beat 调度器才会执行。
- 管理命令 `python manage.py register_periodic_tasks` 会遍历 `INSTALLED_APPS` 中的每个应用，查找其下的 `periodic_tasks` 模块；若该模块定义了 `register_periodic_tasks()`，则调用它。各应用通过项目中的 `core.periodic_registry` 声明 cron 项，该命令再将这些项写入 django_celery_beat 的数据库表（幂等）。

### 在 `docker/entrypoint.sh` 中的生效方式

- entrypoint 会设置 `PYTHONPATH=/opt/devmind` 和 `DJANGO_SETTINGS_MODULE=core.settings`，这样在通过 `-A core` 启动 Celery 时，会加载 `core.celery`，且能正确使用 Django 配置（含 `INSTALLED_APPS`）。
- **`celery`（worker）** 与 **`celery-beat`**：容器执行 `celery -A core worker` 或 `celery -A core beat` 时，导入 `core.celery` 会执行 `autodiscover_tasks()`，所有 app 的 `tasks.py` 被加载，任务对 worker 和 beat 可见；beat 使用 `DatabaseScheduler`，从数据库读取调度表。
- **`gunicorn`** 与 **`development`**：在 `wait_for_db` 和 `run_migrations` 之后，entrypoint 会执行 `python manage.py register_periodic_tasks`（或 true）。该命令会汇总各 app 的 `periodic_tasks.register_periodic_tasks()` 并写入 django_celery_beat。典型多容器部署下，由 Web 容器（gunicorn）在启动时执行一次迁移和 `register_periodic_tasks`；celery 与 celery-beat 容器共用同一数据库，因此无需再执行该命令即可看到已注册的任务与调度。

## 开发环境

### 环境要求

- Docker 与 Docker Compose
- Git

### 搭建步骤

0. **若为克隆得到的仓库**：请先执行 `git submodule update --init --recursive`（见上文 [Agentcore 子模块](#克隆仓库后请先拉取子模块)）。

1. 复制环境配置：

```bash
cp env.sample .env.dev
```

2. 配置环境变量：

编辑 `.env.dev`，按需配置数据库、AI 服务等。

3. 启动服务：

```bash
docker-compose -f docker-compose.dev.yml up -d
```

4. 访问地址：

- 前端：http://localhost:8000
- API 文档：http://localhost:8000/swagger/
- 管理后台：http://localhost:8000/admin/
- Celery 监控：http://localhost:5555

## 生产环境

### 环境要求

- Docker 与 Docker Compose
- 服务器资源建议：至少 4 核 CPU、8GB 内存

### 部署步骤

1. 复制环境配置：

```bash
cp env.sample .env
```

2. 配置生产环境变量：

编辑 `.env`，配置例如：

- `SECRET_KEY`：Django 密钥（生产环境务必修改）
- `DJANGO_DEBUG=false`：关闭调试
- `ALLOWED_HOSTS`：允许的域名
- `CSRF_TRUSTED_ORIGINS`：可信域名
- 数据库（推荐 PostgreSQL，或 MySQL/MariaDB 以兼容旧环境）
- AI 服务（OpenAI / Azure OpenAI 等）
- 其他生产所需配置

3. 启动服务：

```bash
docker-compose up -d
```

4. 查看服务状态：

```bash
docker-compose ps
```

5. 查看日志：

```bash
docker-compose logs -f
```

### 默认端口

- HTTP：10080
- HTTPS：10443

可通过 `.env` 中的 `NGINX_HTTP_PORT`、`NGINX_HTTPS_PORT` 修改端口。
