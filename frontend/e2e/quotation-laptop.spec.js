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
    sessionStorage.setItem('app_sidebar_collapsed', 'true')
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
      await expect(
        page.getByText(/All quotes\. Signed in as|全部报价.*当前登录用户/),
      ).toHaveCount(0)
      const listStageOverflow = await page.evaluate(() => {
        const stage = document.querySelector('#app-scroll-stage')
        if (!stage) return null
        const style = getComputedStyle(stage)
        return {
          overflowX: style.overflowX,
          scrollWidth: stage.scrollWidth,
          clientWidth: stage.clientWidth,
        }
      })
      expect(listStageOverflow).not.toBeNull()
      expect(listStageOverflow.overflowX).toBe('hidden')
      expect(listStageOverflow.scrollWidth).toBeLessThanOrEqual(
        listStageOverflow.clientWidth + 1,
      )
      const quoteRows = page.locator('[data-quotation-row]')
      if ((await quoteRows.count()) >= 10) {
        const tenRowsFit = await page.evaluate(() => {
          const rows = [...document.querySelectorAll('[data-quotation-row]')]
          const stage = document.querySelector('#app-scroll-stage')
          if (rows.length < 10 || !stage) return false
          return (
            rows[9].getBoundingClientRect().bottom <=
            stage.getBoundingClientRect().bottom + 1
          )
        })
        expect(tenRowsFit, 'ten quote rows fit in the list viewport').toBe(true)
      }

      const projectHeader = page.locator('[data-column-header="project"]')
      const projectResizer = page.locator(
        '[data-column-resizer][data-column-key="project"]',
      )
      if (await projectResizer.isVisible().catch(() => false)) {
        const beforeWidth = await projectHeader.evaluate(
          (element) => element.getBoundingClientRect().width,
        )
        const handleBox = await projectResizer.boundingBox()
        expect(handleBox).not.toBeNull()
        await page.mouse.move(
          handleBox.x + handleBox.width / 2,
          handleBox.y + handleBox.height / 2,
        )
        await page.mouse.down()
        await page.mouse.move(
          handleBox.x + handleBox.width / 2 + 96,
          handleBox.y + handleBox.height / 2,
          { steps: 5 },
        )
        await page.mouse.up()
        const draggedWidth = await projectHeader.evaluate(
          (element) => element.getBoundingClientRect().width,
        )
        expect(draggedWidth).toBeGreaterThan(beforeWidth + 80)

        await projectResizer.focus()
        await page.keyboard.press('ArrowLeft')
        const keyboardWidth = await projectHeader.evaluate(
          (element) => element.getBoundingClientRect().width,
        )
        expect(keyboardWidth).toBeLessThan(draggedWidth)
      }

      const pageSizeTrigger = page.getByTestId('quotation-page-size')
      if (await pageSizeTrigger.isVisible().catch(() => false)) {
        await pageSizeTrigger.click()
        const pageSizeMenu = page.getByTestId('quotation-page-size-menu')
        await expect(pageSizeMenu).toBeVisible()
        const menuIsVisible = await pageSizeMenu.evaluate((element) => {
          const rect = element.getBoundingClientRect()
          return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.right <= window.innerWidth &&
            rect.bottom <= window.innerHeight
          )
        })
        expect(menuIsVisible, 'page-size menu is not clipped').toBe(true)
        await page.keyboard.press('Escape')
      }

      const importedRow = page
        .locator('[data-quotation-row][data-source-type="document_import"]')
        .first()
      if (await importedRow.isVisible().catch(() => false)) {
        const listUrl = page.url()
        await importedRow.click()
        await expect(page.locator('[data-quotation-detail-drawer]')).toBeVisible()
        await expect(page.locator('#quote-details-root')).toBeVisible()
        await expect(page.locator('[data-embedded-quotation-preview]')).toBeVisible()
        await expect(page.locator('[data-quotation-details-sidebar]')).toHaveCount(0)
        const drawerOverflow = await page.evaluate(() => {
          const drawerScroll = document.querySelector(
            '[data-quotation-drawer-scroll]',
          )
          const preview = document.querySelector(
            '[data-embedded-quotation-preview]',
          )
          return {
            scrollbarWidth: drawerScroll
              ? getComputedStyle(drawerScroll).scrollbarWidth
              : null,
            drawerClientHeight: drawerScroll?.clientHeight ?? null,
            drawerScrollHeight: drawerScroll?.scrollHeight ?? null,
            previewClientHeight: preview?.clientHeight ?? null,
            previewScrollHeight: preview?.scrollHeight ?? null,
          }
        })
        expect(drawerOverflow.scrollbarWidth).toBe('none')
        expect(drawerOverflow.drawerScrollHeight).toBeGreaterThan(
          drawerOverflow.drawerClientHeight,
        )
        expect(drawerOverflow.previewScrollHeight).toBeLessThanOrEqual(
          drawerOverflow.previewClientHeight + 1,
        )
        expect(page.url()).toBe(listUrl)
        const detailsAudit = await auditLaptopLayout(page)
        expect(detailsAudit.pageOverflow, 'details has page overflow').toBe(false)
        expect(detailsAudit.clippedControls, 'details has clipped text').toEqual([])
        expect(detailsAudit.offscreenControls, 'details has offscreen controls').toEqual([])
        await page.screenshot({
          path: `${screenshotRoot}/${language}-${viewport.width}-collapsed-details.png`,
          fullPage: false,
        })
        await page.keyboard.press('Escape')
        await expect(page.locator('[data-quotation-detail-drawer]')).toHaveCount(0)
        await expect(importedRow).toBeFocused()
      } else {
        const firstQuoteAction = page.locator('[data-view-details]').first()
        if (await firstQuoteAction.isVisible().catch(() => false)) {
          await firstQuoteAction.click()
          await expect(page.locator('#quote-details-root')).toBeVisible()
        }
      }
    })
  }
}
