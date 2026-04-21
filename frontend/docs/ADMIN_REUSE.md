# Admin 模块复制与接入说明

将 DevMind 管理后台（admin）复制到新项目后，按本文完成接入即可使用同一套管理界面。

## 1. 复制内容

- 直接复制整个 **`src/admin/`** 目录到新项目的 `src/admin/`。
- 目录结构包括：`layout/`、`pages/`、`api/`、`locales/`、`routes.js`。

## 2. 前置依赖

新项目需具备：

- **技术栈**：Vue 3、Vue Router、Pinia、Vue I18n、axios。
- **Store**：`store/user` 需提供：
  - `userInfo.is_staff`（是否管理员）
  - `checkAuth()`、`isAuthenticated`
- **通用 UI**：`@/components/ui` 下的 BaseButton、BaseLoading、BaseModal、StatusBadge 等（或接口兼容的等价组件）。
- **Composables**：`useToast`（可选 `useDebounce`）；**Utils**：`@/utils/api`（如 `extractErrorMessage`、`extractResponseData`）、`@/utils/formatting`（如 `formatNumLocale`、`formatCostLocale`、`formatDateIsoLocale`）。
- **LLM 相关页**：若使用 LLM Config 等页，需有 `@/components/llm/ProviderIcon`、`@/components/ui/MarkdownRenderer`（或占位实现）。

## 3. 接入步骤

### 3.1 路由

在主路由文件中：

- `import { adminRoutes } from '@/admin/routes'`
- 在 404 / catch-all 之前将 admin 路由展开，例如：`routes = [ ...otherRoutes, ...adminRoutes, { path: '/404', ... }, { path: '/:pathMatch(.*)*', ... } ]`
- 确保路由守卫中保留对 **`meta.requiresAdmin`** 和 **`userInfo.is_staff`** 的检查（与 DevMind 主应用一致）。

### 3.2 i18n

- 在主应用 i18n 初始化处合并 admin 的 locale：
  - `import adminEn from '@/admin/locales/en.json'`
  - `import adminZhCN from '@/admin/locales/zh-CN.json'`
  - 将二者合并进对应 locale 的 messages（例如 `messages.en = { ...mainEn, ...adminEn }`），避免覆盖已有 key 时可使用深合并。

### 3.3 API 与环境

- 配置 API base URL（如 `VITE_API_BASE_URL` 或项目内 `src/config/api.js` / `src/api/index.js` 使用的 baseURL）。
- Admin 模块内 API 使用 `@/api/index` 的客户端，因此新项目需有统一的 axios 实例（或等价）并配置好 baseURL。

## 4. 后端差异说明

- Admin 默认面向 **DevMind 风格** 后端（如 `/v1/admin/llm-usage/`、`/v1/admin/notifications/...`、`/v1/management/users|groups`、`/v1/tasks/...`）。
- 若新项目后端路径或契约不同，需在复制后的 **`admin/api/*.js`** 中按新后端修改请求路径或请求/响应格式。

## 5. 使用 Skill 一键接入（推荐）

复制完 `src/admin/` 后，可将本仓库的 **`.agents/skills/admin-integration`**（或 `.cursor/skills/admin-integration` 等）复制到目标项目的对应 skills 目录，或放到个人 `~/.cursor/skills/`、`~/.codex/skills/`、`~/.claude/skills/`。在 Cursor / Codex / Claude Code 中让 AI 根据该 skill 按步骤完成路由、i18n、依赖检查与 API 配置，即可将 admin 接到可用状态。
