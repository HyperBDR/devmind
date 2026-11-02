import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

import {
  notificationRuleDefaults,
  notificationRulePayload,
  resolveNotificationRules,
  dailyReportLabel
} from '../src/components/agione-demo/notification-rules.mjs'

test('daily report status describes the real stage', () => {
  assert.equal(dailyReportLabel({ status: 'collecting' }), '采集中')
  assert.equal(dailyReportLabel({ status: 'analyzing' }), '分析中')
  assert.equal(dailyReportLabel({ status: 'sent' }), '已发送')
  assert.equal(dailyReportLabel({ status: 'no_alert' }), '无符合条件的事项')
  assert.equal(dailyReportLabel({ status: 'failed' }), '处理失败')
})

test('unconfigured server rules migrate valid browser thresholds', () => {
  const resolved = resolveNotificationRules(
    { ...notificationRuleDefaults, configured: false, channels: [] },
    {
      inactivityDays: 11,
      declinePercent: 33,
      technicalFailurePercent: 4,
      minTechnicalRequests: 25
    }
  )

  assert.equal(resolved.inactivityDays, 11)
  assert.equal(resolved.declinePercent, 33)
  assert.equal(resolved.analysisDays, 7)
})

test('configured server rules always win over stale browser values', () => {
  const resolved = resolveNotificationRules(
    {
      ...notificationRuleDefaults,
      configured: true,
      inactivityDays: 9,
      channels: []
    },
    { inactivityDays: 20 }
  )

  assert.equal(resolved.inactivityDays, 9)
})

test('save payload excludes response metadata and preserves sending switch', () => {
  const payload = notificationRulePayload({
    ...notificationRuleDefaults,
    configured: true,
    channels: [{ id: 'secret', name: 'not config' }],
    enabled: true,
    channelId: '9dcc43d1-81c9-4f73-9c34-6d1fb359ee83'
  })

  assert.equal(payload.enabled, true)
  assert.equal('configured' in payload, false)
  assert.equal('channels' in payload, false)
  assert.equal(payload.analysisDays, 7)
  assert.equal(payload.scheduleTime, '01:20')
  assert.equal(payload.repeatHours, 4)
  assert.equal(payload.sendRecovery, true)
  assert.equal(payload.eventWindowMinutes, 120)
  assert.equal(payload.autoRefreshEnabled, false)
  assert.equal(payload.autoRefreshHours, 3)
  assert.equal(payload.financeRefreshHours, 12)
  assert.equal(payload.tenantRefreshHours, 12)
  assert.equal(payload.sendRecoveredHistory, true)
  assert.equal(payload.failureRatePercent, 80)
  assert.equal(payload.minBalanceFailureCount, 1)
})

test('rule dialog exposes auto periods, recovered history and split status', () => {
  const source = fs.readFileSync(
    new URL('../src/components/agione-demo/FocusWorkspace.vue', import.meta.url),
    'utf8'
  )

  assert.match(source, /每 2 小时/)
  assert.match(source, /每 3 小时/)
  assert.match(source, /每 4 小时/)
  assert.match(source, /发送已恢复的历史异常/)
  assert.match(source, /财务/)
  assert.match(source, /租户/)
  assert.match(source, /巡检/)
})
