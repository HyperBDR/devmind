# 报价单 Excel/PDF 异步导出流水线

报价单文件由后端固定版本快照生成。浏览器不再构造 Excel，也不再把
工作簿上传到同步 PDF 接口。

## 处理流程

1. `POST /api/v1/quotation/quotations/{id}/exports` 固定
   `QuotationVersion`、`QuotationTemplate`、渲染器版本和输出格式。
2. `backend-worker` 从 `quotation_render` 队列读取任务，使用 `openpyxl`
   填充命名区域，并在独立 LibreOffice profile 中转换 PDF。
3. 所有请求格式都成功后，XLSX/PDF 才会保存为独立 `DocumentAsset`。
4. 启用归档时，数据库提交后再把每个资产投递到 `quotation_sync` 队列。
5. 同步任务通过 `StorageRouter` 解析固定 `StorageMount`，上传飞书并更新
   `DocumentReplica`。上传失败不会重新渲染，也不会删除本地资产。

渲染任务只执行当前代码支持的 renderer 版本。部署升级后仍滞留在队列中的
旧 renderer 任务会以 `renderer_version_unsupported` 失败；重新提交导出请求
会按当前版本创建新的固定任务，避免用新实现生成却标记成旧版本的文件。

任务状态包括 `queued`、`rendering_excel`、`converting_pdf`、
`upload_queued`、`uploading`、`completed`、`render_failed` 和
`upload_failed`。`upload_failed` 可调用
`POST /api/v1/quotation/exports/{job_id}/retry-upload` 单独重试。

## 部署

统一的 Backend Worker 使用 Docker target `backend-render`，其中包含
Excel/PDF 解析依赖、LibreOffice Calc、Noto CJK 和 Liberation 字体，并
同时消费 `backend`、`quotation_sync`、`quotation_excel`、
`quotation_pdf` 和 `quotation_render` 队列。API 与调度器镜像不安装
LibreOffice。OCR 仍由可选的独立 Worker 处理。

renderer 版本由代码实现固定，并自动参与导出幂等键，不能通过环境变量
覆盖。渲染行为变化时必须随代码递增版本常量。

关键配置：

- `QUOTATION_SOFFICE_BINARY`：默认 `soffice`。
- `QUOTATION_RENDER_TIMEOUT_SECONDS`：单次转换硬超时，默认 120 秒。
- `CELERY_CONCURRENCY`：统一 Worker 的并发数，需要同时考虑普通任务、
  文档解析和 LibreOffice 转换的内存占用。
- `QUOTATION_MAX_TEMPLATE_BYTES`、`QUOTATION_MAX_TEMPLATE_EXPANDED_BYTES`：
  输入模板的压缩体积和展开体积上限。
- `QUOTATION_MAX_PDF_BYTES`：输出 PDF 上限。
- `QUOTATION_MAX_SIGNATURE_BYTES`：快照签名图片解码后的大小上限。
- `QUOTATION_STORAGE_ROUTER_ENABLED` 与
  `QUOTATION_DOCUMENT_REPLICA_ENABLED`：控制固定目录归档能力。

生产环境升级顺序：先迁移数据库，再启动 API 和统一 Backend Worker。
Worker 或飞书不可用时，API 仍可启动并处理同步请求以外的业务；飞书失败
的导出仍可从本地资产下载。

## 模板约定

模板必须是无宏、无外部连接的 `.xlsx`，包含 `Quotation` 工作表及后端
校验的命名区域。模板内容哈希必须与 `QuotationTemplate.content_hash`
一致。Fresh deploy 在首次导出时创建并激活标准模板；自定义模板应作为
新的不可变版本登记，旧版本只归档、不覆盖。

标准模板 v2 增加 `tax_label` 与 `vat_rate` 命名区域。升级环境首次导出时
只会把内容指纹匹配的标准模板 v1 归档并激活 v2；已激活的同名或异名
自定义模板均不受影响。

管理员可通过 `POST /api/v1/quotation/templates` 以 multipart 方式上传
`name`、`version`、`status` 与 `file`。后端会在登记前执行完整模板校验；
激活新版本时，已有活动模板自动转为归档状态。`GET` 同一路径可查看模板
版本清单。

## 故障排查

- 长时间停在 `queued`：确认 `backend-worker` 正在消费
  `quotation_render`，并检查 Redis 连接。
- `libreoffice_timeout`：检查 Worker 内存、字体和输入模板；任务最多自动
  重试一次。
- `template_*`：属于数据或模板错误，不自动重试；校验工作表、命名区域、
  宏、外部连接和文件哈希。
- `upload_failed`：检查 `StorageConnection`、`StorageMount` 和飞书权限，
  修复后只调用 retry-upload；不要重新提交渲染任务。
- Worker 渲染失败：在 Backend Worker 容器内非交互执行
  `soffice --headless --version`，并确认 `/opt/storage` 可写。
- `GET /api/v1/quotation/metrics/exports`：查看共享缓存记录的渲染与归档
  成功、失败、重试次数及累计耗时；结构化日志同时包含任务级耗时与稳定
  错误码。

旧 Gotenberg 服务、`GOTENBERG_*` 配置、浏览器 ExcelJS 生成器以及
`/pdf/from-excel`、`/pdf/from-html` 同步接口已随前端切换一并移除。
