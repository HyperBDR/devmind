import { test, expect } from '@playwright/test'

test('rule settings show safe collection status and heartbeat', async ({ page }) => {
  const module = await page.request.get('/src/components/agione-demo/FocusWorkspace.vue')
  test.skip(!module.headers()['content-type']?.includes('javascript'), 'Requires the Vite development server')
  await page.route('**/v1/agione-ops/connections/test/notification-rules/', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data: {
      configured: true, channels: [], recentRuns: [{
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
