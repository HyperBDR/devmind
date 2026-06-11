# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

DevMind 是 AI 驱动的企业内部门户平台，包含 Django REST API 后端与 Vue 3 前端。核心能力：

- **云账单**（cloud_billing）：多云厂商账单聚合（AWS/Azure/阿里云/华为云/腾讯云/火山/百度/智谱等），各厂商在 `clouds/` 目录下独立 Provider 适配
- **数据采集**（data_collector）：从 JIRA、飞书等系统拉取原始数据
- **AI 模型价格中心**（ai_pricehub + llm_ops）：价格对比、LangChain/LLM parser、多厂商价格采集
- **运维控制台**（sals、hyperbdr_dashboard）：事件管理、统计、HyperBDR 迁移看板
- **统一基础设施**（agentcore 子模块）：LLM 用量追踪、统一任务管理、飞书通知

两个并行子系统（git submodules）位于 `sals/backend`、`sals/frontend` 下，与主仓解耦。

## 常用命令

### 初始化（克隆后必执行）
```bash
git submodule update --init --recursive
```

### 本地开发（Docker）
```bash
cp env.sample .env.dev
docker-compose -f docker-compose.dev.yml up -d
# Web http://localhost:8000  Swagger /swagger/  Admin /admin/  Flower :5555
```

### 生产部署
```bash
cp env.sample .env
APP_VERSION=1.2.3 docker-compose up -d
# 默认端口 HTTP 10080 / HTTPS 10443
```

### 非 Docker 开发
```bash
pip install -e .[dev]
for d in backend/agentcore/*/; do [ -f "${d}pyproject.toml" ] && pip install -e "$d"; done
```

### 后端测试与质量
```bash
pytest                              # 全部测试
pytest path/to/test.py -k test_xyz  # 单测试/单文件
pytest -m unit                      # 跑 unit marker
black --check backend/
isort --check backend/
flake8 backend/
```

### Django 管理命令
```bash
python backend/manage.py migrate
python backend/manage.py register_periodic_tasks   # 写 django_celery_beat；已有记录不覆盖
python backend/manage.py createsuperuser
python backend/manage.py shell -c "..."            # 非交互模式（勿用裸 shell）
```

### 前端
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build
npm run lint         # ESLint 自动修复
npm run test:e2e     # Playwright
```

环境变量：`VITE_API_BASE_URL`、`VITE_APP_TITLE`、`VITE_API_TIMEOUT`

## 架构概览

### Django 应用结构

每个 app **自包含**：`models.py` + `serializers.py` + `services.py` + `views/` 或 `views.py` + `tasks.py` + `periodic_tasks.py`（可选）+ `tests/` + `migrations/`。跨 app 回归测试在 `backend/tests/`。

主要 app（按 `backend/core/urls.py` 路由顺序）：

| App | 路由前缀 | 关键能力 |
|---|---|---|
| `accounts` | `/accounts/`, `/_allauth/` | dj-rest-auth (JWT) + django-allauth (Google OAuth) + Headless API；Profile/Role/Permission |
| `cloud_billing` | `/api/v1/cloud-billing/` | `clouds/` 下多厂商 Provider 适配；`agents/`、`skills/` 用于账单分析 |
| `ai_pricehub` | `/api/v1/ai-pricehub/` | `vendors/` 多家价格源；LangChain + LLM 抽取；`vendor_pricing_common.py` 共享模型 |
| `llm_ops` | `/api/v1/llm-ops/` | 渠道/价格源/对账工作台；`collectors/` 自动采集；`seed_data` 种子数据 |
| `data_collector` | `/api/v1/data-collector/` | JIRA / 飞书原始数据；attachments、统计 API |
| `hyperbdr_dashboard` | `/api/v1/hyperbdr-dashboard/` | HyperBDR 迁移看板；含 `client.py` 外部接口、`encryption.py` |
| `sals` | `/api/v1/sals/` | 事件管理 / 统计 |
| `agentcore_metering` | `/api/v1/admin/` | LLM 用量追踪（mounted before admin） |
| `agentcore_task` | `/api/v1/tasks/` | 统一任务管理 |
| `agentcore_notifier` | `/api/v1/admin/notifications/` | 飞书通知（must come before admin/） |

注意 `core/urls.py` 的 `admin/notifications/` 路由必须排在 `admin/` 之前以正确匹配。

### 共享基础设施（`backend/core/`）

- **`settings/` 分片**：`base.py` + 专题模块（`database.py`、`celery.py`、`rest.py`、`swagger.py`、`accounts.py`、`cache.py`、`ai_services.py`、`langfuse.py`、`sentry.py`、`logging_config.py`、`middlewares.py`、`renders.py`），按主题拆分避免单文件过大
- **`urls.py`**：根路由 + health check + Swagger/Redoc + OAuth 回调拦截（必须早于 `allauth.urls`）
- **`celery.py`**：Celery app；`on_worker_process_init` 信号里**懒加载** `autodiscover_tasks`，避免 app 未完全加载就发现任务；显式 `imports=` 列表预先注册关键任务
- **`periodic_registry.py`**：`TaskRegistry` 内存注册器；`apply()` 写入 `django_celery_beat`。**已存在的 PeriodicTask 不会被覆盖**（保护运维人员手动修改）
- **`middleware.py`**：含 `LanguageCodeMappingMiddleware` 把浏览器 Accept-Language 映射到 `zh-hans`/`en`
- **`swagger.py`、`renders.py`**：DRF 自定义渲染器 / OpenAPI schema

### Celery 任务与定时任务

- **任务发现**：worker 启动后由 `on_worker_process_init` 懒调用 `app.autodiscover_tasks()`，按 `apps.get_app_configs()` 遍历能 `import .tasks` 的 app
- **定时任务**：`register_periodic_tasks` management command 找到每个 app 的 `periodic_tasks.register_periodic_tasks()`，把条目 push 到 `TASK_REGISTRY` 后调用 `apply_registry()` 写入 DB
- **celery-beat**：用 `DatabaseScheduler` 从 DB 读调度，不读代码
- **容器编排**（`docker/entrypoint.sh`）：gunicorn 容器 `wait_for_db → migrate → createsuperuser → register_periodic_tasks → start`；celery/celery-beat 容器只 `wait_for_db` 后启动，复用同一 DB

### 业务逻辑位置

业务逻辑放在 `models.py`、`serializers.py`、`services.py`，**views 只做请求处理**。复杂逻辑用 CBV，简单逻辑可用 FBV。

### API 层

- DRF + drf-spectacular（OpenAPI 3 + Swagger UI + ReDoc）
- 错误追踪：`sentry-sdk` 在 `core/settings/sentry.py` 集成
- 观测：Langfuse 集成（`ai_services.py`、`langfuse.py`）
- WebSocket：Channels + daphne（ASGI），Redis channel layer
- 时区：DB 存 UTC，前端做时区转换（`date-fns-tz`）
- i18n：中文（`zh-hans`）和英文（`en`），通过自定义中间件映射浏览器语言

### 前端（`frontend/`）

- Vue 3 + Vite + Composition API + `<script setup>`
- 状态：Pinia；路由：vue-router；i18n：vue-i18n；UI：Tailwind CSS + Headless UI
- 图表：Chart.js + vue-chartjs；Markdown：marked + DOMPurify；日期：@vuepic/vue-datepicker
- ECharts 由 `chart.js` + `vue-chartjs` 替代
- E2E：Playwright（`playwright.config.cjs`）
- 源码组织：`src/{api,components,composables,config,constants,i18n,locales,pages,router,store,utils,mock,assets}`

## 编码规范（来自 Cursor rules `python-rules.mdc`）

- **语言**：所有解释**中文**，代码注释**英文**（注释写在代码块上方，禁内联注释；类/函数用 docstring 三引号）
- **行宽**：每行最多 **79 字符**
- **Import 结构**（三段式，段间空行，段内字母序）：
  1. 标准库
  2. 第三方库
  3. 本地 app（用绝对导入，禁在 import 上写注释）
- **Django/DRF**：CBV 处理复杂逻辑；ORM 操作；DRF Serializer；views 只处理请求；select_related/prefetch_related 优化；Redis 缓存
- **错误处理**：view 层用 try-except + DRF 异常；DRF validation framework 校验
- **依赖**：Django 5.1.4 / DRF 3.15.2 / Celery 5.3.1 / Redis / PostgreSQL 或 MySQL
- **终端非交互**（`run-command-in-terminal.mdc`）：禁止 `bash`、`docker exec -it`、`python`、`python manage.py shell`、`npm install`、`git add` 无参等交互式命令；全部用 `-c`/`--yes`/`git add <file>` 形式

## 安全与配置

- **不提交** `.env`、secrets、证书；从 `env.sample` 复制创建
- 生产推荐 PostgreSQL（psycopg2-binary），MySQL 备选（`mysqlclient` 已弃用，改 PyMySQL）
- `docker/nginx/certs/` 与云厂商配置文件发布前需审查
- 多租户关键凭据（如 HyperBDR）使用 `encryption.py` 加密

## 设计原则

每个 app 必须**自管资源**（DB 表、API、配置、测试、定时任务）。详细见 `docs/DESIGN_PRINCIPLES.md` / `docs/DESIGN_PRINCIPLES.zh-CN.md`。
