# 报价模块 · 飞书云盘联调配置指南

本文说明 **报价单上传 Excel/PDF 到飞书云盘** 需要如何配置。
（群机器人 Webhook 通知见 `backend/agentcore/agentcore-notifier/docs/FEISHU_WEBHOOK.md`，与本文无关。）

---

## 1. 角色分工

| 角色 | 做什么 |
|------|--------|
| 飞书开放平台管理员 | 创建/维护 **1 个**企业自建应用，开通权限，配置回调地址，提供 App ID / App Secret |
| 运维 / 开发 | 把凭证写入服务器或本地 `.env`，保证 `FRONTEND_URL` / 回调一致 |
| 普通业务用户 | 在报价系统里点一次「连接飞书」，用自己的飞书账号授权，选择上传文件夹 |

员工 **不需要** 每人建一个应用。公司共用一个应用，每人各自完成用户授权。

本地个人联调：可用自己的测试企业自建应用；正式上线应换成公司租户下由管理员创建的应用。

---

## 2. 整体流程

```text
管理员创建飞书自建应用
        ↓
开通云盘相关权限 + 发布/可用范围
        ↓
配置重定向 URL（OAuth 回调）
        ↓
把 App ID / App Secret 写入环境变量
        ↓
用户登录报价系统 →「连接飞书」→ 飞书授权页同意
        ↓
回调写入 FeishuConnection（用户 token）
        ↓
浏览云盘 / 选择文件夹 → 上传 Excel 或 PDF
```

关键 API 路径（均挂在 `/api/v1/quotation/` 下）：

| 用途 | 路径 |
|------|------|
| 连接状态 | `GET /feishu/status` |
| 开始授权 | `GET /feishu/oauth/start` |
| OAuth 回调 | `GET /feishu/oauth/callback` |
| 浏览文件夹 | `GET /feishu/folder` |
| 上传文件 | `POST /feishu/upload` |
| 设置默认文件夹 | `PUT /feishu/preferred-folder` |

授权成功后后端会重定向回发起授权时的 Quote Desk 页面，例如：
`{FRONTEND_URL}/quotation/imports?feishu=connected`。

---

## 3. 飞书开放平台操作步骤

### 3.1 创建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/)
2. 进入你的企业（测试可用个人测试企业；正式用公司租户）
3. 创建 **企业自建应用**
4. 记录：
   - **App ID**
   - **App Secret**

### 3.2 开通权限（必开）

在应用「权限管理」中申请并开通以下权限（与代码默认 `FEISHU_OAUTH_SCOPES` 一致）：

| 权限 / Scope | 用途 |
|--------------|------|
| `drive:drive` | 访问云盘 |
| `drive:file` | 读写云盘文件元数据 |
| `drive:file:upload` | 上传文件到云盘 |
| `drive:file:download` | 下载云盘文件 |
| `drive:export:readonly` | 导出相关只读能力 |
| `docs:document:export` | 文档导出（缺省时上传/导入可能报权限错误） |
| `search:docs:read` | 搜索可见云文档/文件夹（用于发现共享文件夹） |
| `offline_access` | 刷新 token，避免频繁重新授权 |

说明：

- 权限开通后，通常需要 **发布版本** 或把应用加到测试人员可用范围，否则普通账号授权会失败。
- 若接口返回缺少导出权限（如错误码 `99991679`），优先检查 `drive:export:readonly` / `docs:document:export` 是否已生效，并让用户 **重新连接飞书** 以刷新授权 scope。

### 3.3 配置安全设置 · 重定向 URL

在应用「安全设置」→「重定向 URL」中添加 **与环境完全一致** 的回调地址。

默认规则（未单独设置 `FEISHU_OAUTH_REDIRECT_URI` 时）：

```text
{FRONTEND_URL}/api/v1/quotation/feishu/oauth/callback
```

#### 本仓库当前本地开发（`.env.dev`）

`FRONTEND_URL=http://localhost:18000`，因此回调为：

```text
http://localhost:18000/api/v1/quotation/feishu/oauth/callback
```

#### 其他常见环境示例

| 环境 | 示例回调 |
|------|----------|
| 本地 nginx 18000 | `http://localhost:18000/api/v1/quotation/feishu/oauth/callback` |
| 默认文档里的 8000 | `http://localhost:8000/api/v1/quotation/feishu/oauth/callback` |
| 生产 HTTPS | `https://你的域名/api/v1/quotation/feishu/oauth/callback` |

注意：

- 协议、域名、端口、路径必须与环境变量一致，多一个斜杠或 http/https 不一致都会导致 OAuth 失败。
- 飞书开放平台填写的 redirect_uri，必须与后端实际使用的 `FEISHU_OAUTH_REDIRECT_URI` 字符串完全相同。

### 3.4 可用范围

- 开发/联调：把测试账号加入应用可用成员，或发布测试版。
- 公司内部全员：按公司规范发布应用，并设置可见范围（全员或指定部门）。

### 3.5 浏览我的文件夹 / 共享文件夹

报价云盘面板左侧对齐飞书「云盘」结构：

1. **我的文件夹**：自动列出你「我的空间」根下的目录（例如 `test`）。
2. **共享文件夹**：飞书开放平台没有公开的「共享文件夹根目录」列表接口。面板会：
   - 只展示共享空间根目录（`parentId=0`，如 Tower），与飞书侧栏一致
   - 点击文件夹前的箭头可展开下级目录（如 Tower → **From Evelyn）
   - 用已固定的共享根目录书签展示（粘贴根目录链接 →「打开并固定」）
   - 若用户已授权 `search:docs:read`，尽量通过搜索自动发现可见根目录
   - 打开嵌套子目录不再写入侧栏根列表，避免与飞书侧栏不一致的平铺书签
3. **上传**：仍需进入具体文件夹后「设为上传目录 / 上传到此目录」。

改权限或新增 `search:docs:read` 后，请在面板点「重新授权」。

---

## 4. 本项目环境变量

建议在 `.env.dev` / `.env` 中配置（可参考 `env.sample`）：

```bash
# 必填：开放平台应用凭证
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 开放平台 API 根（一般不用改）
FEISHU_AUTH_BASE_URL=https://open.feishu.cn
# 或
FEISHU_BASE_URL=https://open.feishu.cn

# 前端入口（用于默认回调与授权成功跳转）
FRONTEND_URL=http://localhost:18000

# 可选：显式指定回调（不填则用 FRONTEND_URL + 固定路径）
# FEISHU_OAUTH_REDIRECT_URI=http://localhost:18000/api/v1/quotation/feishu/oauth/callback

# 可选：覆盖 OAuth scope（默认已包含云盘上传所需权限）
# FEISHU_OAUTH_SCOPES=drive:drive drive:file drive:file:upload drive:file:download drive:export:readonly docs:document:export search:docs:read offline_access

# 可选：无法解析「我的空间」时的兜底文件夹 token
# FEISHU_TEST_FOLDER_TOKEN=
```

改完环境变量后需 **重启后端 API 容器/进程** 才会生效。

可通过状态接口确认是否识别到凭证：

```bash
# 需已登录拿到 JWT 后调用
GET /api/v1/quotation/feishu/status
```

返回里关注：

- `configured: true` → App ID / Secret 已配置
- `connected: true` → 当前用户已完成授权
- `redirect_uri` → 当前后端实际使用的回调，应与开放平台一致

---

## 5. 业务侧怎么测

1. 本地或测试环境启动报价前后端，用系统账号登录。
2. 进入报价列表，对某条报价点上传飞书（或打开飞书云盘弹窗）。
3. 若未连接，先点 **连接飞书**，浏览器跳转飞书授权页，同意权限。
4. 授权成功后回到发起授权时的 Quote Desk 页面，并带上
   `feishu=connected` 提示参数。
5. 在弹窗中浏览文件夹，选中目标目录，上传 Excel / PDF。
6. 上传成功后，报价状态会变为 Uploaded，并可在历史版本中看到对应记录。

建议先用自己有写权限的个人文件夹或测试文件夹验证，再测共享目录。

---

## 6. 常见问题

| 现象 | 排查 |
|------|------|
| `Feishu credentials are not configured` | `.env` 未填 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，或未重启服务 |
| 授权后报 redirect_uri 不匹配 | 开放平台回调与 `FEISHU_OAUTH_REDIRECT_URI` / `FRONTEND_URL` 不一致 |
| `OAuth user not found` | state 里的邮箱与系统用户 email/username 对不上；用同一邮箱登录系统 |
| 缺少导出权限 / `99991679` | 开放平台开通导出相关权限后，用户需重新「连接飞书」 |
| 能授权但不能上传 | 检查 `drive:file:upload`；确认对目标文件夹有写权限 |
| 本地回调打不开 | 确认 nginx/API 已监听 `FRONTEND_URL` 对应端口（本仓库开发常用 `18000`） |

---

## 7. 个人测试 vs 公司正式环境

| | 个人联调 | 公司内部正式使用 |
|--|----------|------------------|
| 应用归属 | 自己测试企业自建应用 | 公司租户自建应用（管理员创建） |
| 凭证 | 开发者自己的 App ID/Secret | 运维写入生产/测试环境变量 |
| 回调 | `localhost` 或测试域名 | 正式 HTTPS 域名 |
| 用户 | 开发者自己授权 | 全员各自授权一次 |
| 建议 | 勿把个人 Secret 提交进 Git | Secret 只放环境变量 / 密钥系统 |

---

## 8. 相关代码位置

- 设置默认值：`backend/core/settings/base.py`（`FEISHU_*`）
- OAuth / 上传：`backend/quotation/views/feishu.py`
- 飞书客户端：`backend/quotation/services/feishu_client.py`
- 前端弹窗与连接：`frontend/src/modules/quotation/components/FeishuDriveModal.vue`
- 前端 API：`frontend/src/modules/quotation/api/feishu.ts`
