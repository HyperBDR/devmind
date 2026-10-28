# AGIOne 原生接入与部署

AGIOne 替代 `/llm-ops` 的前端入口。LLM Operations 的历史数据库与后端
不会因路由替换而自动删除。AGIOne 业务数据只使用被授权的原生连接；不要
在生产启用本地 Demo 配置或使用 `core.settings.agione_local`。

## 密钥与环境

在生产环境的受控密钥管理系统中准备独立的 Fernet 加密密钥，设置以下
环境变量并确保 API、worker 和后台初始化容器读取相同的配置：

```text
AGIONE_OPS_NATIVE_ENABLED=true
AGIONE_OPS_NATIVE_ONLY=true
AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=agione.pro,agione.cc
AGIONE_OPS_ENCRYPTION_KEY=<从密钥管理系统注入的 Fernet 密钥>
AGIONE_OPS_ACTIVE_KEY_ID=agione-v1
AGIONE_OPS_FINANCE_REFRESH_ON_SYNC=false
```

不要把真实密钥、AK/SK、凭据 JSON 或数据库转储放入 Git、构建参数、
镜像、终端历史或任务日志。保持密钥和 key ID 稳定并进行安全备份；更换
密钥前须重新加密现有凭据，否则已有密文将无法解密。若从本地复用 AK/SK，
通过受控秘密渠道传递凭据，在生产环境用生产密钥重新加密；不要把本地
数据库密文当作无需密钥即可迁移的配置。

## 初始化连接和授权

完成部署并执行数据库迁移后，向 `import_agione_native_credentials` 命令
的标准输入提供 JSON 数组；示例中的值均为占位符：

```json
[
  {
    "platform": "pro",
    "principal_kind": "provider",
    "endpoint": "https://agione.pro",
    "expected_tenant_id": "123456",
    "credentials": {
      "auth_mode": "aksk",
      "access_key": "<从密钥管理系统获取>",
      "secret_key": "<从密钥管理系统获取>",
      "api_prefix": "/hyperone",
      "username": "<原生账号用户名>",
      "shost": "<原生网关路由标识>",
      "static_route": "<原生静态路由标识>"
    }
  }
]
```

按实际需要提供 Pro/CC 的 Provider 和 Operator 连接，最多四条；租户 ID
应从原生账号核实，不依赖 Demo 数据。需要财务汇总时，同平台同地址的
Operator 连接也要授权给该用户。连接创建仅校验配置，不代替首次采集时
对上游账号身份的验证。

使用有权限的安全输入通道，将凭据 JSON 作为标准输入送给 API 容器内的：

```text
python manage.py import_agione_native_credentials --user-id <用户ID> --allow-sync
```

命令默认只授予指定用户查看权；`--allow-sync` 明确授予该用户发起同步的
权限，`--allow-manage` 可另外授予管理连接的动作权限。重复导入不会撤销
已有同步权限。不要在命令参数中填写 AK/SK。其他用户必须分别获得连接
授权和对应动作权限；普通用户还需要由管理员在 DevMind 角色管理中启用
`agione_ops` 功能。功能可见不等于业务数据访问授权。

## 首次采集和核验

确认 API、Celery worker、Redis 和数据库均正常，且 worker 注册了
`agione_ops.tasks.run_sync` 与 `agione_ops.tasks.refresh_native_finance`。
首次导入并授予采集权限或验证连接时，如果当前账号有查看和采集权限且
尚无快照，会自动提交最近 7 天采集；也可手动点击“刷新数据”。生产数据库
不会自动包含本机快照；调用数据发布后，财务在后台独立采集。核验三个页面的
日期范围、客户范围、财务覆盖与采集时间；没有 Operator 授权时财务显示
不可用，不补零。首次采集或选中未采集的日期可能耗时，后续已采集范围
内查询使用本地数据。

财务采集默认读取本月和上月的日数据；账期摘要分别显示入账与消耗的
实际覆盖日期，不完整的日期不会按零计算。更早日期能否获取取决于上游
接口，目前不在默认采集范围内。

回退财务同步模式时可设置 `AGIONE_OPS_FINANCE_REFRESH_ON_SYNC=true`，
并重启 API 与 worker；此模式下调用快照需要等待财务采集完成。

### 查询与采集调度

- 日期筛选最多 31 个完整自然日。查询会复用同连接、同配置版本的已发布快照；部分日期缺失时标记不完整，并通过现有后台任务补采。
- 默认同时采集 2 个日期（`AGIONE_OPS_NATIVE_SHARD_CONCURRENCY`，范围 1–3）；每个任务默认最多运行 120 秒（`AGIONE_OPS_NATIVE_MAX_SECONDS`，范围 30–1800）。已完成的暂存分片可在 24 小时内续用。
- 定时任务 `agione_recent_data_prefetch` 每天北京时间 01:20 使用具有查看、采集权限的有效授权预采最近 7 个完整自然日。若没有符合条件的授权或连接正忙则跳过；调度配置在 Celery Beat 中管理。
- `agione_staging_cleanup` 每天北京时间 02:20 清理已成功发布或已终止、保留超过 30 天的临时采集记录；`AGIONE_OPS_STAGING_RETENTION_DAYS` 可调整，最少 7 天。已发布快照和未完成任务的数据不在此清理范围。
- `agione_snapshot_cleanup` 每天北京时间 02:40 清理超过 90 天（按发布时间）的正式快照内容，保留版本及任务记录；`AGIONE_OPS_SNAPSHOT_RETENTION_DAYS` 可调整，最少 30 天。每个连接保留最新快照，查询使用的各快照在最近一次访问后保护 24 小时；过期历史数据需要重新采集。
