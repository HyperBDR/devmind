# 报价模块 · 飞书云盘配置指南

本文说明 Quote Desk 的飞书云盘如何配置。当前方案是 **系统托管的固定归档文件夹**：后端使用同一个飞书应用访问指定文件夹，用户在系统里只能上传报价文件或刷新导入，不需要填写文件夹链接，也不需要个人飞书授权。

---

## 1. 角色分工

| 角色 | 做什么 |
|------|--------|
| 飞书开放平台管理员 | 创建/维护企业自建应用，开通云盘文件读写权限，提供 App ID / App Secret |
| 飞书文件夹管理员 | 创建报价归档文件夹，并确保自建应用有访问该文件夹的权限 |
| 运维 / 开发 | 把应用凭证和固定文件夹链接写入 `.env.dev` / `.env` |
| 普通业务用户 | 在 Quote Desk 中上传报价文件，或刷新导入固定文件夹里的文件 |

普通用户不填写飞书文件夹链接，也不会选择个人云盘目录。

---

## 2. 整体流程

```text
管理员创建飞书自建应用
        ↓
开通云盘文件读写/下载/导出权限
        ↓
创建或指定一个报价归档文件夹
        ↓
把 App ID / App Secret / 文件夹链接写入环境变量
        ↓
用户在 Quote Desk 上传 Excel/PDF
        ↓
后端使用系统应用上传到固定飞书文件夹
        ↓
Import Queue 点击 Refresh，可同步固定文件夹里的 Excel/PDF 到系统
```

关键 API 路径（均挂在 `/api/v1/quotation/` 下）：

| 用途 | 路径 |
|------|------|
| 飞书配置状态 | `GET /feishu/status` |
| 上传报价文件到固定文件夹 | `POST /feishu/upload` |
| 同步固定文件夹中的文件 | `POST /feishu/sync-folder` |
| 检查飞书文件是否仍存在 | `GET /feishu/files/<file_token>/access` |
| 下载/读取已关联飞书文件 | `GET /feishu/files/<file_token>/content` |

旧的个人 OAuth 和目录选择接口仍保留路由兼容，但不会再执行用户授权或文件夹选择。

---

## 3. 飞书开放平台配置

### 3.1 创建应用

1. 打开飞书开放平台。
2. 在目标企业下创建企业自建应用。
3. 记录 App ID 和 App Secret。

### 3.2 开通权限

应用至少需要覆盖以下能力：

| 能力 | 用途 |
|------|------|
| 云盘文件元数据读取 | 判断文件是否存在、读取文件名和类型 |
| 云盘文件上传 | 将报价 Excel/PDF 上传到固定归档文件夹 |
| 云盘文件下载 / 导出 | 从固定归档文件夹导入 Excel/PDF |

权限调整后，通常需要发布应用版本或确保应用在目标企业内可用。

### 3.3 固定归档文件夹

在飞书中创建一个专门用于报价归档的文件夹，例如：

```text
Quote Desk Archive
```

然后复制该文件夹链接，配置到后端环境变量：

```bash
QUOTATION_FEISHU_ARCHIVE_FOLDER_URL=https://example.feishu.cn/drive/folder/xxxxxxxx
```

也可以只配置文件夹 token：

```bash
QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN=xxxxxxxx
```

如果两个都配置，系统优先使用 `QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN`。

---

## 4. 本项目环境变量

建议在 `.env.dev` / `.env` 中配置：

```bash
# 必填：飞书开放平台应用凭证
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 一般不用改
FEISHU_AUTH_BASE_URL=https://open.feishu.cn
# 或
FEISHU_BASE_URL=https://open.feishu.cn

# 必填：报价模块固定飞书归档文件夹
QUOTATION_FEISHU_ARCHIVE_FOLDER_URL=https://example.feishu.cn/drive/folder/xxxxxxxx
# 或
# QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN=xxxxxxxx
```

改完环境变量后，需要重建或重启后端 API / worker / scheduler 容器，环境变量才会生效。

可用以下方式确认配置是否被识别：

```bash
GET /api/v1/quotation/feishu/status
```

返回里关注：

- `configured: true`：App ID / App Secret / 固定文件夹已配置。
- `connected: true`：系统飞书归档能力可用。
- `mode: system_archive_folder`：当前是系统固定文件夹模式。

---

## 5. 业务侧测试

1. 启动 DevMind，并登录 Quote Desk。
2. 创建或打开一条报价单。
3. 上传 Excel 或 PDF 到飞书。
4. 到固定飞书归档文件夹确认文件出现。
5. 在飞书删除该文件，再回到系统触发文件状态检查，确认对应的打开按钮会消失。
6. 手动把 Excel/PDF 放入固定飞书归档文件夹。
7. 进入 Import Queue，点击 Refresh，确认新文件被同步到系统列表。

---

## 6. 常见问题

| 现象 | 排查 |
|------|------|
| `Feishu credentials are not configured` | `.env` 未配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，或后端未重启 |
| `Quotation Feishu archive folder is not configured` | 未配置 `QUOTATION_FEISHU_ARCHIVE_FOLDER_URL` 或 `QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN` |
| 上传失败 | 检查应用是否有上传权限，以及固定文件夹是否允许该应用写入 |
| 导入失败 | 检查应用是否有下载/导出权限，且文件在固定归档文件夹内 |
| 系统里还能看到已删除文件按钮 | 触发一次文件状态检查或刷新列表，系统会清理失效的飞书链接 |

---

## 7. 相关代码位置

- 飞书配置：`backend/core/settings/quotation.py`
- 飞书上传/同步/检查接口：`backend/quotation/views/feishu/`
- 飞书客户端：`backend/quotation/services/feishu_client.py`
- 前端 API：`frontend/src/modules/quotation/api/feishu.ts`
- 导入队列页面：`frontend/src/modules/quotation/components/ImportedDocumentsPage.vue`
- 报价列表上传入口：`frontend/src/modules/quotation/components/QuotationList.vue`
