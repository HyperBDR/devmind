# DevMind

[English](README.md) | 中文

面向企业内部使用的 AI 加速平台，支持 AI 驱动的研发项目管理、财务数据分析等智能工作流。

## Agentcore 子模块

通用模块（如 LLM 追踪、配置、任务管理、通知等）以独立仓库维护，通过 **Git 子模块** 引入到 `devmind/agentcore/` 下。项目以可编辑方式安装并使用这些包，不再在本地保留兼容层。

### 克隆仓库后：请先拉取子模块

**若你刚克隆本仓库，必须先初始化并拉取子模块**，否则 agentcore 包不可用，Python 导入和 Django 应用会报错。

```bash
git submodule update --init --recursive
```

### 安装 agentcore 包（本地与 CI）

`devmind/agentcore/` 下每个子模块均为可 pip 安装的包。建议以可编辑模式安装，以便项目能导入 `agentcore_xxx`：

```bash
# 在仓库根目录（devmind/）下执行
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

Docker 构建会在安装主依赖后，在 Dockerfile 中执行相同逻辑。

### 子模块与用法对照

| 子模块               | 替代（已废弃） | Django 应用 (INSTALLED_APPS)       | 导入 / URL 挂载           |
|----------------------|----------------|------------------------------------|----------------------------|
| `agentcore-tracking` | llm_tracker    | `agentcore_tracking.adapters.django` | `agentcore_tracking.*`、`api/v1/admin/` |

后续子模块（如 agentcore-config、agentcore-task-tracker、agentcore-notifier）将沿用相同方式安装与使用。

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
