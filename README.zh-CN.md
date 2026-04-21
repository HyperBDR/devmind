# DevMind

[English](README.md) | 中文

面向企业内部使用的 AI 加速平台，支持 AI 驱动的研发项目管理、财务数据分析等智能工作流。

## 架构总览

```
devmind/
├── backend/               # Django REST API
│   ├── core/              # 项目配置（settings/、urls.py、celery.py、periodic_registry.py）
│   ├── accounts/          # 用户认证、Profile、Role、Permission
│   ├── cloud_billing/     # 云账单管理（AWS / Azure / 阿里云 / 华为云 / 腾讯云）
│   ├── data_collector/   # 从 JIRA、飞书等系统拉取原始数据
│   ├── ai_pricehub/      # AI 模型价格对比
│   ├── app_config/        # 全局配置（Feature Flag）
│   └── agentcore/        # Git 子模块
│       ├── agentcore-metering/   # LLM 用量追踪  → /api/v1/admin/
│       ├── agentcore-task/       # 统一任务管理   → /api/v1/tasks/
│       └── agentcore-notifier/   # 飞书通知       → /api/v1/admin/notifications/
└── frontend/              # Vue 3（Vite + Pinia + Tailwind + vue-i18n）
```

**技术栈要点**：
- 所有数据存储均为 UTC，前端负责用户本地时区转换
- 每个 Django app 自包含（models、views、serializers、services、migrations、tests 自管）
- 定时任务通过 `periodic_tasks.register_periodic_tasks()` 注册，写入 django_celery_beat；现有记录不会被覆盖

## 快速上手

### 1. 拉取子模块（克隆后必做）

```bash
git submodule update --init --recursive
```

### 2. 配置并启动（Docker 开发）

```bash
cp env.sample .env.dev
# 编辑 .env.dev，按需配置数据库、AI 服务
docker-compose -f docker-compose.dev.yml up -d
```

### 3. 访问服务

| 服务 | 地址 |
|---|---|
| Web UI | http://localhost:8000 |
| API 文档 | http://localhost:8000/swagger/ |
| 管理后台 | http://localhost:8000/admin/ |
| Celery 监控 | http://localhost:5555 |

### 4. 常用开发命令

```bash
# Backend
pytest                                    # 运行所有测试
pytest path/to/test.py                    # 单个测试文件
black --check backend/                    # 检查代码格式
isort --check backend/                    # 检查 import 顺序

# Django 管理
python backend/manage.py migrate
python backend/manage.py register_periodic_tasks   # 注册定时任务
python backend/manage.py createsuperuser

# Frontend
cd frontend && npm install
npm run dev          # 开发服务器
npm run build        # 生产构建
npm run lint
npm run test:e2e     # Playwright E2E
```

## Agentcore 子模块详解

通用模块（LLM 追踪、任务管理、通知）以独立 Git 仓库维护，作为子模块引入。

### 安装方式对照

| 环境 | 方式 |
|---|---|
| 生产（Docker） | `pyproject.toml` 依赖指向 GitHub，镜像构建时自动安装 |
| 开发（Docker） | `DEV_MODE=1` 镜像额外执行 `pip install -e .` 覆盖本地 agentcore |
| 本地 / 非 Docker | 克隆后手动 `pip install -e "$d"`（见下方） |

### 本地可编辑安装

```bash
for d in backend/agentcore/*/; do
  [ -f "${d}pyproject.toml" ] && pip install -e "$d"
done
```

### 子模块映射

| 子模块 | Django app (INSTALLED_APPS) | URL 前缀 |
|---|---|---|
| `agentcore-metering` | `agentcore_metering.adapters.django` | `/api/v1/admin/` |
| `agentcore-task` | `agentcore_task.adapters.django` | `/api/v1/tasks/` |
| `agentcore-notifier` | `agentcore_notifier.adapters.django` | `/api/v1/admin/notifications/` |

## Celery 任务加载与定时任务机制

### 任务发现

`core/celery.py` 调用 `app.autodiscover_tasks()`，自动加载 `INSTALLED_APPS` 中每个 app 的 `tasks.py`。只要在 `INSTALLED_APPS` 中且提供 `tasks.py` 的 Django app 都会被自动发现，无需额外配置。

### 定时任务注册

定时任务不依赖 Celery 自动发现，而是通过 `python manage.py register_periodic_tasks` 写入 **django_celery_beat** 数据库：

1. 遍历 `INSTALLED_APPS` 中每个 app，查找 `periodic_tasks` 模块
2. 若该模块定义了 `register_periodic_tasks()`，调用它
3. 各 app 使用 `core.periodic_registry` 声明 cron 项
4. 注册器**只创建缺失记录**，已存在的 django_celery_beat 记录保持不变

### entrypoint.sh 中的执行顺序

| 容器 | 行为 |
|---|---|
| gunicorn / development | `wait_for_db` → `migrate` → `register_periodic_tasks` → 启动服务 |
| celery | `wait_for_db` → 启动 worker（`autodiscover_tasks` 加载 tasks） |
| celery-beat | `wait_for_db` → 启动 beat（`DatabaseScheduler` 从数据库读取调度表） |

典型多容器部署下，gunicorn 容器执行一次 `register_periodic_tasks`；celery / celery-beat 共用同一数据库，无需重复执行。

## 设计原则

为解耦，**每个应用（app）应自行管理自身资源**，包括数据库、接口、配置等。详见 [docs/DESIGN_PRINCIPLES.zh-CN.md](docs/DESIGN_PRINCIPLES.zh-CN.md)。  
Design principles (English): [docs/DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md).

## 生产环境

```bash
cp env.sample .env
# 编辑 .env：SECRET_KEY、DJANGO_DEBUG=false、ALLOWED_HOSTS、数据库、AI 服务等
APP_VERSION=1.2.3 docker-compose -f docker-compose.yml up -d
```

**默认端口**：HTTP 10080、HTTPS 10443（通过 `NGINX_HTTP_PORT`、`NGINX_HTTPS_PORT` 修改）

> 生产镜像版本由 `APP_VERSION` 决定。打 tag 发布时，GitHub Actions 会自动
> 把 `v1.2.3` 转成 `APP_VERSION=1.2.3`，再执行 `docker-compose pull` 和
> `docker-compose up -d`。手工部署时也要显式传这个变量，否则 compose 会
> 因为 `APP_VERSION is required` 直接失败。

## 前端

- Vue 3 + Composition API + `<script setup>`
- Vite + Pinia + Vue Router + vue-i18n + Tailwind CSS
- E2E：Playwright

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # Docker 构建使用根目录 Dockerfile frontend target
```

环境变量：`VITE_API_BASE_URL`、`VITE_APP_TITLE`、`VITE_API_TIMEOUT`
