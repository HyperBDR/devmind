export function syncJobError(job) {
  if (job.error_message) return job.error_message
  const failedResults = Object.values(job.results || {}).filter(
    (result) => result?.status === 'failed'
  )
  const firstMessage = failedResults[0]?.message
  if (!firstMessage) return '飞书数据同步失败。'
  if (failedResults.length === 1) return firstMessage
  return `${failedResults.length} 张飞书表同步失败：${firstMessage}`
}

export function syncJobFailureDetails(job) {
  const items = Object.entries(job?.results || {})
    .filter(([, result]) => result?.status === 'failed')
    .map(([key, result]) => buildFailureItem(key, result))

  return {
    items,
    summary: syncJobError(job || {}),
  }
}

function buildFailureItem(key, result) {
  const detail = isPlainObject(result.feishu_detail)
    ? result.feishu_detail
    : {}
  const headers = isPlainObject(detail.request_headers)
    ? detail.request_headers
    : {}

  return {
    feishuCode: safeValue(detail.feishu_code),
    feishuMessage: safeText(detail.feishu_msg),
    httpStatus: safeNumber(detail.http_status),
    issueCode: safeText(result.issue_code, 100),
    key: safeText(key, 150),
    logId: firstSafeText(headers, ['x-tt-logid', 'x-log-id']),
    message: safeText(result.message),
    requestId: firstSafeText(headers, [
      'x-request-id',
      'x-lark-request-id',
    ]),
    stage: safeText(detail.stage, 100),
    suggestions: failureSuggestions(result),
    tableUrl: safeFeishuTableUrl(detail.table_url),
  }
}

function failureSuggestions(result) {
  const suggestions = [safeText(result.resolution_hint)]
  const issueCode = result.issue_code || ''

  if (['app_access_denied', 'table_access_denied'].includes(issueCode)) {
    suggestions.push(
      '确认当前飞书应用已添加为目标多维表格的协作者，并具备数据表记录读取权限。',
      '确认 app_token 与 table_id 来自同一个多维表格链接，避免新 base token 搭配旧 table ID。',
      '在飞书开放平台开通 bitable:app:readonly、bitable:record:readonly 和 bitable:field:readonly，发布应用后重新检查。'
    )
  } else if (issueCode === 'token_error') {
    suggestions.push(
      '核对 Data Ops 使用的飞书 App ID 和 Secret，确认应用处于启用状态。',
      '确认容器环境变量与后台全局配置没有指向不同的飞书应用。'
    )
  } else if (issueCode === 'field_missing') {
    suggestions.push(
      '核对源表字段是否被重命名或删除，并同步更新 Data Ops 字段映射。'
    )
  } else if (issueCode === 'config_missing') {
    suggestions.push(
      '使用包含 table 参数的飞书多维表格链接补全 app_token 和 table_id。'
    )
  } else if (issueCode === 'network_error') {
    suggestions.push(
      '检查服务到 open.feishu.cn 的网络、DNS 和代理配置，再重试单表检查。'
    )
  } else if (issueCode === 'pagination_incomplete') {
    suggestions.push(
      '使用请求追踪 ID 检查飞书接口日志，确认分页 token 是否完整返回。'
    )
  } else if (issueCode === 'zero_records_unexpected') {
    suggestions.push(
      '检查源表数据量、视图过滤和应用可见范围是否发生变化。'
    )
  }

  suggestions.push(
    '保存配置后先执行“检查”，再进行单表同步；确认通过后再运行全量同步。'
  )
  return [...new Set(suggestions.filter(Boolean))]
}

function safeFeishuTableUrl(value) {
  try {
    const url = new URL(String(value || ''))
    const allowedHosts = new Set(['feishu.cn', 'www.feishu.cn'])
    if (
      url.protocol !== 'https:' ||
      !allowedHosts.has(url.hostname) ||
      !url.pathname.startsWith('/base/')
    ) {
      return ''
    }
    return url.toString()
  } catch {
    return ''
  }
}

function firstSafeText(values, keys) {
  for (const key of keys) {
    const value = safeText(values[key], 200)
    if (value) return value
  }
  return ''
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function safeNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function safeText(value, maxLength = 1000) {
  if (value === null || value === undefined) return ''
  return String(value).slice(0, maxLength)
}

function safeValue(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  return safeText(value, 100)
}
