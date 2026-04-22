/**
 * E2E tests for Cloud Billing pages: Providers, Billing, Tasks, Alerts.
 * Requires authenticated user with operations_console feature.
 */
import { test, expect } from '@playwright/test'

async function login(page) {
  const username = process.env.TEST_USERNAME || 'admin'
  const password = process.env.TEST_PASSWORD || 'admin'

  await page.goto('/login')
  await page.waitForLoadState('networkidle')

  const loginForm = page.locator('form').first()
  const formVisible = await loginForm.isVisible().catch(() => false)
  if (!formVisible) return false

  await page.fill('input[name="username"]', username)
  await page.fill('input[name="password"]', password)
  await page.click('button[type="submit"]')
  await page.waitForLoadState('networkidle')
  return !page.url().includes('/login')
}

test.describe('Cloud Billing Providers', () => {
  test.use({
    baseURL:
      process.env.BASE_URL ||
      process.env.PLAYWRIGHT_BASE_URL ||
      'http://localhost:10080'
  })

  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Providers page renders table or empty state', async ({ page }) => {
    await page.goto('/cloud-billing/providers')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/cloud-billing\/providers/)
    const title = page.locator('h1').first()
    await expect(title).toBeVisible({ timeout: 10000 })
    const tableOrEmpty = page
      .locator('table, text=/暂无|no provider|no providers/i')
      .first()
    await expect(tableOrEmpty).toBeVisible({ timeout: 10000 })
  })

  test('Create Provider button is visible', async ({ page }) => {
    await page.goto('/cloud-billing/providers')
    await page.waitForLoadState('networkidle')
    const createBtn = page
      .locator('button', { hasText: /create|新增|添加/i })
      .first()
    await expect(createBtn).toBeVisible({ timeout: 10000 })
  })

  test('Providers table has expected columns', async ({ page }) => {
    await page.goto('/cloud-billing/providers')
    await page.waitForLoadState('networkidle')
    // Wait for either table headers or empty state
    const table = page.locator('table')
    const hasTable = await table.isVisible().catch(() => false)
    if (hasTable) {
      await expect(page.locator('th').first()).toBeVisible()
    } else {
      await expect(page.locator('text=/暂无|no provider/i')).toBeVisible()
    }
  })
})

test.describe('Cloud Billing - Billing page', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Billing page loads with tabs', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/cloud-billing\/billing/)
    const tabBar = page.locator('nav[aria-label], .border-b button').first()
    await expect(tabBar).toBeVisible({ timeout: 10000 })
  })

  test('Statistics tab is active by default', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    const defaultTab = page
      .locator('button', { hasText: /statistics|统计/i })
      .first()
    await expect(defaultTab).toBeVisible({ timeout: 5000 })
  })

  test('switches between Statistics and Details tabs', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    const detailsTab = page
      .locator('button', { hasText: /details|明细/i })
      .first()
    await detailsTab.click()
    await page.waitForLoadState('networkidle')

    // Details tab should now be active
    await expect(detailsTab).toHaveClass(/border-primary|text-primary/)
  })

  test('Statistics tab shows filters', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    const periodSelect = page.locator('select').first()
    await expect(periodSelect).toBeVisible({ timeout: 10000 })
  })

  test('Details tab shows search and date filters', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    await page
      .locator('button', { hasText: /details|明细/i })
      .first()
      .click()
    await page.waitForLoadState('networkidle')

    await expect(page.locator('input[type="date"]').first()).toBeVisible({
      timeout: 5000
    })
    await expect(
      page
        .locator('input[placeholder*="search" i]')
        .or(page.locator('input[type="search"]'))
        .first()
    ).toBeVisible({ timeout: 5000 })
  })

  test('Details tab shows table or empty state', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    await page
      .locator('button', { hasText: /details|明细/i })
      .first()
      .click()
    await page.waitForLoadState('networkidle')

    const tableOrEmpty = page.locator('table, text=/暂无|no data/i').first()
    await expect(tableOrEmpty).toBeVisible({ timeout: 15000 })
  })

  test('pagination controls exist when data is present', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    await page
      .locator('button', { hasText: /details|明细/i })
      .first()
      .click()
    await page.waitForLoadState('networkidle')

    // Give it time to load data
    await page.waitForTimeout(2000)

    const pagination = page.locator('text=/showing|page/i').first()
    const paginationVisible = await pagination.isVisible().catch(() => false)
    if (paginationVisible) {
      await expect(page.locator('select').last()).toBeVisible()
    }
  })

  test('refresh button is present', async ({ page }) => {
    await page.goto('/cloud-billing/billing')
    await page.waitForLoadState('networkidle')

    const refreshBtn = page
      .locator('button[title*="refresh" i], button svg[class*="rotate"]')
      .first()
    await expect(refreshBtn).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Cloud Billing Tasks', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Tasks page loads', async ({ page }) => {
    await page.goto('/cloud-billing/tasks')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/cloud-billing\/tasks/)
  })
})

test.describe('Cloud Billing Alerts', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Alerts page loads', async ({ page }) => {
    await page.goto('/cloud-billing/alerts')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/cloud-billing\/alerts/)
  })
})

test.describe('Cloud Billing Settings', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Settings page loads', async ({ page }) => {
    await page.goto('/cloud-billing/settings')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/cloud-billing\/settings/)
  })

  test('Recharge info save requires submitter identifier', async ({ page }) => {
    let patchCalls = 0

    await page.route('**/v1/cloud-billing/providers**', async (route) => {
      const url = new URL(route.request().url())
      const pathname = url.pathname
      const method = route.request().method()

      if (method === 'GET' && pathname === '/v1/cloud-billing/providers/') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [
              {
                id: 1,
                name: 'Test Provider',
                provider_type: 'zhipu',
                display_name: 'Test Provider',
                auth_identifier: 'test@example.com',
                is_active: true,
                created_at: '2026-04-21T00:00:00Z',
                recharge_info: JSON.stringify({
                  cloud_type: '智谱',
                  recharge_customer_name: '深圳壹铂云科技有限公司',
                  recharge_account: '18017606559',
                  payment_company: '深圳壹铂云科技有限公司',
                  payment_way: '公司支付',
                  payment_type: '仅充值',
                  remit_method: '转账',
                  payee: {
                    type: '对公账户',
                    account_name: '北京智谱华章科技股份有限公司',
                    account_number: '11093851041070210011884',
                    bank_name: '招商银行',
                    bank_region: '北京市/北京市',
                    bank_branch: '招商银行股份有限公司北京上地支行'
                  }
                }),
                config: {}
              }
            ],
            count: 1
          })
        })
        return
      }

      if (
        method === 'GET' &&
        pathname === '/v1/cloud-billing/providers/tags/'
      ) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ tags: [] })
        })
        return
      }

      if (method === 'GET' && pathname === '/v1/cloud-billing/providers/1/') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            name: 'Test Provider',
            provider_type: 'zhipu',
            display_name: 'Test Provider',
            auth_identifier: 'test@example.com',
            is_active: true,
            created_at: '2026-04-21T00:00:00Z',
            recharge_info: JSON.stringify({
              cloud_type: '智谱',
              recharge_customer_name: '深圳壹铂云科技有限公司',
              recharge_account: '18017606559',
              payment_company: '深圳壹铂云科技有限公司',
              payment_way: '公司支付',
              payment_type: '仅充值',
              remit_method: '转账',
              payee: {
                type: '对公账户',
                account_name: '北京智谱华章科技股份有限公司',
                account_number: '11093851041070210011884',
                bank_name: '招商银行',
                bank_region: '北京市/北京市',
                bank_branch: '招商银行股份有限公司北京上地支行'
              }
            }),
            config: {}
          })
        })
        return
      }

      if (method === 'PATCH' && pathname === '/v1/cloud-billing/providers/1/') {
        patchCalls += 1
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true })
        })
        return
      }

      await route.continue()
    })

    await page.route('**/v1/cloud-billing/alert-rules**', async (route) => {
      const request = route.request()
      if (
        request.method() === 'GET' &&
        new URL(request.url()).pathname === '/v1/cloud-billing/alert-rules/'
      ) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: [] })
        })
        return
      }

      await route.continue()
    })

    await page.goto('/cloud-billing/settings')
    await page.waitForLoadState('networkidle')

    await page
      .locator('button[title*="充值审批"], button[title*="Recharge Approval"]')
      .first()
      .click()

    const rechargeInfoField = page.locator('#providerRechargeInfo')
    await expect(rechargeInfoField).toBeVisible({ timeout: 10000 })
    await rechargeInfoField.fill(`{
  "cloud_type": "智谱",
  "recharge_customer_name": "深圳壹铂云科技有限公司",
  "recharge_account": "18017606559",
  "payment_company": "深圳壹铂云科技有限公司",
  "payment_way": "公司支付",
  "payment_type": "仅充值",
  "remit_method": "转账",
  "payee": {
    "type": "对公账户",
    "account_name": "北京智谱华章科技股份有限公司",
    "account_number": "11093851041070210011884",
    "bank_name": "招商银行",
    "bank_region": "北京市/北京市",
    "bank_branch": "招商银行股份有限公司北京上地支行"
  }
}`)

    await page
      .getByRole('button', { name: /保存|Save/i })
      .last()
      .click()

    await expect(
      page.locator('[role="alert"]').filter({
        hasText:
          /请先填写发起人的邮箱或手机号|Enter the submitter email address or mobile number first/i
      })
    ).toBeVisible({ timeout: 5000 })
    await expect.poll(() => patchCalls).toBe(0)
  })
})
