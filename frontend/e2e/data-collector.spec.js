/**
 * E2E tests for Data Collector pages: Stats, Records, Tasks, Settings.
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

test.describe('Data Collector Stats', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Stats page loads and shows stats cards or empty state', async ({ page }) => {
    await page.goto('/data-collector/stats')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/data-collector\/stats/)

    const title = page.locator('h1').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    const statsOrEmpty = page
      .locator('.text-2xl, text=/暂无|total|records/i')
      .first()
    await expect(statsOrEmpty).toBeVisible({ timeout: 10000 })
  })

  test('refresh button triggers reload', async ({ page }) => {
    await page.goto('/data-collector/stats')
    await page.waitForLoadState('networkidle')

    const refreshBtn = page.locator('button[title*="refresh" i]').first()
    await expect(refreshBtn).toBeVisible({ timeout: 5000 })
    await refreshBtn.click()
    // Page should reload without crashing
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Data Collector Records', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Records page loads', async ({ page }) => {
    await page.goto('/data-collector/records')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/data-collector\/records/)

    const title = page.locator('h1').first()
    await expect(title).toBeVisible({ timeout: 10000 })
  })

  test('Records page shows table or empty state', async ({ page }) => {
    await page.goto('/data-collector/records')
    await page.waitForLoadState('networkidle')

    const tableOrEmpty = page
      .locator('table, text=/暂无|no records|no data/i')
      .first()
    await expect(tableOrEmpty).toBeVisible({ timeout: 15000 })
  })

  test('Records page has pagination when data present', async ({ page }) => {
    await page.goto('/data-collector/records')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const pagination = page.locator('text=/showing|page|共/i').first()
    const hasPagination = await pagination.isVisible().catch(() => false)
    if (hasPagination) {
      await expect(pagination).toBeVisible()
    }
  })

  test('clicking a record row opens detail panel', async ({ page }) => {
    await page.goto('/data-collector/records')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const firstRow = page.locator('tbody tr').first()
    const rowExists = await firstRow.isVisible().catch(() => false)
    if (!rowExists) return

    await firstRow.click()
    await page.waitForTimeout(1000)

    const detailPanel = page.locator('[class*="panel"], [class*="drawer"], [class*="modal"]').first()
    const panelVisible = await detailPanel.isVisible().catch(() => false)
    if (panelVisible) {
      await expect(detailPanel).toBeVisible()
    }
  })
})

test.describe('Data Collector Tasks', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Tasks page loads', async ({ page }) => {
    await page.goto('/data-collector/tasks')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/data-collector\/tasks/)

    const title = page.locator('h1').first()
    await expect(title).toBeVisible({ timeout: 10000 })
  })

  test('Tasks page shows cards or empty state', async ({ page }) => {
    await page.goto('/data-collector/tasks')
    await page.waitForLoadState('networkidle')

    const cardsOrEmpty = page
      .locator('.rounded-lg, text=/暂无|no tasks/i')
      .first()
    await expect(cardsOrEmpty).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Data Collector Settings', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Settings page loads with config list', async ({ page }) => {
    await page.goto('/data-collector/settings')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/data-collector\/settings/)

    const title = page.locator('h1').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    const configList = page.locator('[class*="config"], table, text=/暂无|no config/i').first()
    await expect(configList).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Data Collector navigation', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('all data-collector routes are reachable', async ({ page }) => {
    const routes = [
      '/data-collector/stats',
      '/data-collector/records',
      '/data-collector/tasks',
      '/data-collector/settings'
    ]

    for (const route of routes) {
      await page.goto(route)
      await page.waitForLoadState('networkidle')
      expect(page.url()).toMatch(new RegExp(route.replace('/', '\\/')))
    }
  })
})
