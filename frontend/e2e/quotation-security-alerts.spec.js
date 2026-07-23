import { test, expect } from '@playwright/test'

async function login(page) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(process.env.TEST_USERNAME || 'admin')
  await page
    .getByLabel('Password *')
    .fill(process.env.TEST_PASSWORD || 'adminpassword')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 })
}

const evidence = Array.from({ length: 6 }, (_, index) => ({
  id: index + 1,
  action: 'download',
  module: 'document',
  target_id: `document-${index + 1}`,
  target_label: `BDR130726_R${index + 1}.xlsx`,
  request_id: `request-${index + 1}`,
  ip_address: '198.51.100.24',
  created_at: `2026-07-20T13:4${index}:06Z`,
}))

function alertFixture(status = 'open') {
  return {
    id: 42,
    alert_number: 'SA-2026-00042',
    rule: 'unusual_bulk_downloads',
    severity: 'high',
    status,
    title: 'Unusual bulk downloads',
    reason: '26 quotation files were downloaded within 10 minutes.',
    recommendation: 'Confirm whether the download was authorized.',
    subject_email: 'quotation_user@example.com',
    subject_name: 'quotation_user',
    source_ip: '198.51.100.24',
    device: 'Chrome 138 · macOS',
    trigger_count: 26,
    evidence_count: 26,
    first_detected_at: '2026-07-20T13:48:06Z',
    last_detected_at: '2026-07-20T13:56:06Z',
    acknowledged_at:
      status === 'acknowledged' ? '2026-07-20T14:00:00Z' : null,
    resolved_at: status === 'resolved' ? '2026-07-20T14:02:00Z' : null,
    resolution: status === 'resolved' ? 'authorized_activity' : '',
    resolution_note:
      status === 'resolved' ? 'Confirmed with the sales manager.' : '',
    notify_affected_user: false,
    evidence,
  }
}

async function mockAlerts(page) {
  let currentStatus = 'open'
  await page.route('**/api/v1/quotation/security-alerts**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const isDetail = /\/security-alerts\/42$/.test(url.pathname)
    if (request.method() === 'PATCH') {
      const body = request.postDataJSON()
      currentStatus = body.action === 'acknowledge' ? 'acknowledged' : 'resolved'
      await route.fulfill({
        json: { alert: alertFixture(currentStatus), can_manage: true },
      })
      return
    }
    if (isDetail) {
      await route.fulfill({
        json: { alert: alertFixture(currentStatus), can_manage: true },
      })
      return
    }
    await route.fulfill({
      json: {
        items: [alertFixture(currentStatus)],
        summary: {
          open: currentStatus === 'resolved' ? 0 : 1,
          critical: 0,
          high: currentStatus === 'resolved' ? 0 : 1,
          new_last_24_hours: 1,
          immediate_review: currentStatus === 'resolved' ? 0 : 1,
          affected_users_last_24_hours: 1,
        },
        total: 1,
        page: 1,
        page_size: 20,
        can_manage: true,
      },
    })
  })
}

test.describe('Quote Desk security alerts', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await mockAlerts(page)
  })

  test('review, investigate, and resolve flow is usable', async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 })
    await page.goto('/quotation/audit')
    await page.getByRole('button', { name: /Security Alerts/ }).click()

    await expect(page.getByText('Open alerts', { exact: true })).toBeVisible()
    await expect(page.getByText('Unusual bulk downloads').first()).toBeVisible()
    await expect(page.getByText('26 events').first()).toBeVisible()
    await page.screenshot({ path: '/tmp/devmind-security-alerts-implemented.png' })

    await page.getByRole('button', { name: 'View details' }).click()
    await expect(page.getByText('Why this alert was triggered')).toBeVisible()
    await expect(page.getByText('Evidence timeline · 26 events')).toBeVisible()
    await page.screenshot({ path: '/tmp/devmind-security-alert-detail-implemented.png' })

    await page.getByRole('button', { name: 'Acknowledge' }).click()
    await expect(page.getByText('Acknowledged', { exact: true }).last()).toBeVisible()
    await page.getByRole('button', { name: 'Resolve alert' }).click()
    await expect(page.getByText('Resolve security alert')).toBeVisible()
    await page
      .getByPlaceholder('Describe what you verified and how the alert was handled.')
      .fill('Confirmed with the sales manager.')
    await page.screenshot({ path: '/tmp/devmind-security-alert-resolve-implemented.png' })
    await page.getByRole('button', { name: 'Resolve alert' }).last().click()
    await expect(page.getByText('Resolution recorded')).toBeVisible()
  })

  test('activity and alert views fit a smaller desktop viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/quotation/audit')
    await expect(page.getByRole('button', { name: 'Activity Log' })).toBeVisible()
    await page.getByRole('button', { name: /Security Alerts/ }).click()
    await expect(page.getByText('Open alerts', { exact: true })).toBeVisible()

    const fit = await page.evaluate(() => {
      const root = document.documentElement
      const tabs = [...document.querySelectorAll('button')].filter((button) =>
        ['Activity Log', 'Security Alerts'].some((label) =>
          button.textContent?.includes(label),
        ),
      )
      return {
        pageOverflow: root.scrollWidth > root.clientWidth + 1,
        clippedTabs: tabs.some(
          (tab) => tab.scrollWidth > tab.clientWidth + 1,
        ),
      }
    })

    expect(fit.pageOverflow).toBe(false)
    expect(fit.clippedTabs).toBe(false)
  })
})
