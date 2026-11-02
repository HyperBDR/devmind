export const notificationRuleDefaults = Object.freeze({
  analysisDays: 7,
  inactivityDays: 7,
  declinePercent: 40,
  technicalFailurePercent: 2,
  minTechnicalRequests: 20,
  scheduleTime: '01:20',
  autoRefreshEnabled: false,
  autoRefreshHours: 3,
  financeRefreshHours: 12,
  tenantRefreshHours: 12,
  minFailureCount: 6,
  eventWindowMinutes: 120,
  failureRatePercent: 80,
  minBalanceFailureCount: 1,
  continuousFailure: true,
  balanceFailure: true,
  decline: false,
  inactive: false,
  repeatHours: 4,
  sendRecovery: true,
  sendRecoveredHistory: true,
  channelId: null,
  enabled: false
})

const legacyKeys = [
  'inactivityDays',
  'declinePercent',
  'technicalFailurePercent',
  'minTechnicalRequests'
]

const payloadKeys = Object.keys(notificationRuleDefaults)

export function dailyReportLabel(report) {
  const labels = {
    not_run: '尚未执行', idle: '等待执行', collecting: '采集中',
    analyzing: '分析中', done: '等待发送', no_alert: '无符合条件的事项',
    pending: '等待发送', sending: '发送中', retrying: '发送重试中',
    sent: '已发送', failed: '处理失败', silenced: '未发送',
    collection_retrying: '采集失败，等待重试',
    waiting_scope: '等待租户信息',
  }
  return labels[report?.status] || '状态待确认'
}

export function resolveNotificationRules(server, legacy) {
  const result = { ...notificationRuleDefaults, ...server }
  if (!server?.configured && legacy) {
    for (const key of legacyKeys) {
      if (Number.isFinite(legacy[key]) && legacy[key] > 0) {
        result[key] = legacy[key]
      }
    }
  }
  return result
}

export function notificationRulePayload(value) {
  const result = Object.fromEntries(
    payloadKeys.map((key) => [key, value[key]])
  )
  return result
}
