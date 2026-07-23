import { mkdirSync } from 'node:fs'

import { expect, test } from '@playwright/test'

const screenshotRoot = '/tmp/quote-desk-laptop-qa'
mkdirSync(screenshotRoot, { recursive: true })

async function login(page) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(process.env.TEST_USERNAME || 'admin')
  await page
    .getByLabel('Password *')
    .fill(process.env.TEST_PASSWORD || 'adminpassword')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 })
}

async function setLanguage(page, language) {
  await page.evaluate((nextLanguage) => {
    localStorage.setItem('userLanguage', nextLanguage)
  }, language)
  await page.reload({ waitUntil: 'domcontentloaded' })
}

async function collapseSidebar(page) {
  await page.evaluate(() => {
    localStorage.setItem('app_sidebar_collapsed', 'true')
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
}

async function auditLaptopLayout(page) {
  return page.evaluate(() => {
    const root = document.documentElement
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return (
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        Number(style.opacity) !== 0 &&
        rect.width > 0 &&
        rect.height > 0
      )
    }
    const intentionallyClipped = (element) =>
      element.classList.contains('sr-only') ||
      element.classList.contains('truncate') ||
      [...element.classList].some((name) => name.startsWith('line-clamp-'))

    const textControls = [
      ...document.querySelectorAll(
        'button, [role="button"], h1, h2, h3, h4, label, th',
      ),
    ].filter(visible)
    const clippedControls = textControls
      .filter((element) => {
        if (intentionallyClipped(element)) return false
        return (
          element.scrollWidth > element.clientWidth + 2 ||
          element.scrollHeight > element.clientHeight + 2
        )
      })
      .map((element) => (element.textContent || '').trim())
      .filter(Boolean)

    const interactive = [
      ...document.querySelectorAll(
        'button, [role="button"], input, select, textarea, a[href]',
      ),
    ].filter(visible)
    const offscreenControls = interactive
      .filter((element) => {
        if (element.closest('.overflow-x-auto')) return false
        const rect = element.getBoundingClientRect()
        return rect.left < -1 || rect.right > window.innerWidth + 1
      })
      .map((element) => (element.textContent || element.getAttribute('aria-label') || '').trim())
      .filter(Boolean)

    return {
      pageOverflow: root.scrollWidth > root.clientWidth + 1,
      clippedControls,
      offscreenControls,
    }
  })
}

async function mockAuditEvents(page) {
  await page.route('**/api/v1/quotation/audit-events**', async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            id: 'legacy-quote-module',
            created_at: '2026-07-21T03:24:44Z',
            actor_email: 'admin@example.com',
            actor_name: 'admin',
            actor_type: 'user',
            event_name: 'quote.viewed',
            module: 'quote',
            action: 'view',
            result: 'succeeded',
            target_type: 'quotation',
            target_id: 'quote-id',
            target_label: '',
            summary: '',
            changes: {},
            metadata: {},
            risk_level: 'low',
            reason_code: '',
            ip_address: '',
            request_id: 'request-1',
            trace_id: 'trace-1',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        can_export: true,
      },
    })
  })
}

async function mockSecurityAlerts(page) {
  await page.route('**/api/v1/quotation/security-alerts**', async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            id: 42,
            alert_number: 'SA-2026-00042',
            rule: 'unusual_bulk_downloads',
            severity: 'high',
            status: 'open',
            subject_email: 'quotation_user@example.com',
            subject_name: 'quotation_user',
            source_ip: '198.51.100.24',
            device: 'Chrome 138 · macOS',
            trigger_count: 26,
            evidence_count: 26,
            first_detected_at: '2026-07-20T13:48:06Z',
            last_detected_at: '2026-07-20T13:56:06Z',
            acknowledged_at: null,
            resolved_at: null,
            resolution: '',
            resolution_note: '',
            notify_affected_user: false,
            evidence: [],
          },
        ],
        summary: {
          open: 1,
          critical: 0,
          high: 1,
          new_last_24_hours: 1,
          immediate_review: 1,
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

const pages = [
  { path: '/quotation/dashboard', selector: '#dashboard-root', name: 'dashboard' },
  { path: '/quotation/list', selector: '#quote-list-root', name: 'list' },
  { path: '/quotation/create', selector: '#create-quote-root', name: 'create' },
  { path: '/quotation/catalog', selector: '[data-catalog-layout]', name: 'catalog' },
  { path: '/quotation/audit', selector: 'table', name: 'audit' },
]

for (const viewport of [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
]) {
  for (const language of ['en', 'zh-CN']) {
    test(`${language} fits ${viewport.width}x${viewport.height} laptop viewport`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport)
      await login(page)
      await setLanguage(page, language)
      await mockAuditEvents(page)
      await mockSecurityAlerts(page)
      await collapseSidebar(page)

      for (const target of pages) {
        await page.goto(target.path, { waitUntil: 'domcontentloaded' })
        await expect(page.locator(target.selector).first()).toBeVisible()
        await page.waitForTimeout(250)

        const audit = await auditLaptopLayout(page)
        expect(audit.pageOverflow, `${target.name} has page overflow`).toBe(false)
        expect(audit.clippedControls, `${target.name} has clipped text`).toEqual([])
        expect(audit.offscreenControls, `${target.name} has offscreen controls`).toEqual([])

        await page.screenshot({
          path: `${screenshotRoot}/${language}-${viewport.width}-collapsed-${target.name}.png`,
          fullPage: false,
        })

        if (target.name === 'audit') {
          await page
            .getByRole('button', { name: /Security Alerts|安全告警/ })
            .click()
          await expect(page.getByText(/Open alerts|待处理告警/)).toBeVisible()
          const securityAudit = await auditLaptopLayout(page)
          expect(
            securityAudit.pageOverflow,
            'security alerts has page overflow',
          ).toBe(false)
          expect(
            securityAudit.clippedControls,
            'security alerts has clipped text',
          ).toEqual([])
          expect(
            securityAudit.offscreenControls,
            'security alerts has offscreen controls',
          ).toEqual([])
          await page.screenshot({
            path: `${screenshotRoot}/${language}-${viewport.width}-collapsed-security.png`,
            fullPage: false,
          })
        }
      }

      await page.goto('/quotation/audit', { waitUntil: 'domcontentloaded' })
      await expect(
        page.getByText('quotation.pages.audit.modules.quote'),
      ).toHaveCount(0)
      const moduleCell = page.locator('tbody tr').first().locator('td').nth(2)
      const actionCell = page.locator('tbody tr').first().locator('td').nth(3)
      await expect(moduleCell).toBeVisible()
      await expect(actionCell).toBeVisible()
      const cells = await page.evaluate(() => {
        const row = document.querySelector('tbody tr')
        const module = row?.querySelectorAll('td')[2]?.getBoundingClientRect()
        const action = row?.querySelectorAll('td')[3]?.getBoundingClientRect()
        return module && action
          ? { moduleRight: module.right, actionLeft: action.left }
          : null
      })
      expect(cells).not.toBeNull()
      expect(cells.moduleRight).toBeLessThanOrEqual(cells.actionLeft + 1)

      await page.goto('/quotation/list', { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(750)
      const firstQuoteAction = page
        .locator('#table-panel tbody tr')
        .first()
        .locator('td:last-child button')
        .first()
      if (await firstQuoteAction.isVisible().catch(() => false)) {
        await firstQuoteAction.click()
        await expect(page.locator('#quote-details-root')).toBeVisible()
        const detailsAudit = await auditLaptopLayout(page)
        expect(detailsAudit.pageOverflow, 'details has page overflow').toBe(false)
        expect(detailsAudit.clippedControls, 'details has clipped text').toEqual([])
        expect(detailsAudit.offscreenControls, 'details has offscreen controls').toEqual([])
        await page.screenshot({
          path: `${screenshotRoot}/${language}-${viewport.width}-collapsed-details.png`,
          fullPage: false,
        })
      }
    })
  }
}
