import { test, expect } from '@playwright/test'

test('rule settings show safe collection status and heartbeat', async ({ page }) => {
  const module = await page.request.get('/src/components/agione-demo/FocusWorkspace.vue')
  test.skip(!module.headers()['content-type']?.includes('javascript'), 'Requires the Vite development server')
  let acknowledged = false
  await page.route('**/v1/agione-ops/connections/test/inspection-gap/acknowledge/', route => {
    acknowledged = true
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data: {} }) })
  })
  await page.route('**/v1/agione-ops/connections/test/notification-rules/', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data: {
      configured: true, channels: [], inspectionGap: {
        start: '2026-11-02T00:00:00Z', end: '2026-11-02T00:10:00Z',
        ...(acknowledged ? { status: 'acknowledged' } : {})
      }, inspectionGapHistory: [{
        gapStart: '2026-11-01T00:00:00Z', gapEnd: '2026-11-01T01:00:00Z',
        acknowledgedAt: '2026-11-01T02:00:00Z', skippedUntil: '2026-11-01T02:00:00Z',
        acknowledgedById: 42
      }], recentRuns: [{
        runId: 'test-run', trigger: 'automatic', status: 'interrupted',
        phase: 'interrupted', attempt: 1, errorCode: 'LEASE_EXPIRED',
        createdAt: '2026-11-03T00:49:00Z', heartbeatAt: '2026-11-03T00:51:00Z'
      }, {
        runId: 'finance-1', trigger: 'finance', status: 'succeeded',
        phase: 'finance', attempt: 1, createdAt: '2026-11-03T00:40:00Z',
        finishedAt: '2026-11-03T00:43:00Z'
      }]
    } })
  }))
  await page.goto('/agione')
  await page.evaluate(async () => {
    const { createApp, h, nextTick } = await import('/node_modules/.vite/deps/vue.js')
    const { createI18n } = await import('/node_modules/.vite/deps/vue-i18n.js')
    const { default: Focus } = await import('/src/components/agione-demo/FocusWorkspace.vue')
    const host = document.createElement('div')
    document.body.append(host)
    const app = createApp({ render: () => h(Focus, { state: { connectionId: 'test', filters: {}, customerIds: [] } }) })
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': {} } }))
    app.mount(host)
    await nextTick()
    await nextTick()
    const wrapper = host.querySelector('[data-testid="agione-focus"]')
    const button = document.createElement('button')
    button.setAttribute('data-open-rules', '')
    button.textContent = 'Open test rules'
    wrapper.append(button)
    button.click()
  })
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('巡检存在缺口，请人工核查：')).toContainText('2026/11/2 08:00:00')
  page.once('dialog', prompt => prompt.accept())
  await dialog.getByRole('button', { name: '确认已人工核查' }).click()
  await expect(dialog.getByText('巡检存在缺口，请人工核查：')).not.toBeVisible()
  await dialog.getByText('缺口确认记录（最近 20 条）').click()
  await expect(dialog.getByText(/跳过至/)).toContainText('ID 42')
  await expect(dialog.getByText('自动刷新', { exact: true }).last()).not.toBeVisible()
  await dialog.getByText('最近采集任务').click()
  const row = dialog.locator('.recent-sync').first()
  await expect(row.locator('summary')).toContainText('自动刷新')
  await expect(row.locator('summary')).toContainText('已中断')
  await expect(row.locator('summary')).toContainText('11/03 08:49')
  await expect(row.locator('.recent-sync-detail')).not.toBeVisible()
  await row.locator('summary').click()
  await expect(row.locator('.recent-sync-detail')).toBeVisible()
  await expect(row).toContainText('任务心跳超时，等待恢复')
  await expect(row).toContainText('2026/11/3 08:51:00')
  await row.locator('summary').click()
  await expect(row.locator('.recent-sync-detail')).not.toBeVisible()
  const finance = dialog.locator('.recent-sync').nth(1)
  await expect(finance.locator('summary')).toContainText('财务采集')
  await expect(finance.locator('summary')).toContainText('3 分 0 秒')
})
