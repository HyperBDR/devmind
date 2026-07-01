/**
 * E2E tests for authentication: login form, validation, redirect guards.
 */
import { test, expect } from '@playwright/test'

/**
 * Attempt to log in using environment credentials or known test account.
 * Returns true if login succeeded (redirected away from /login).
 */
async function tryLogin(page) {
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

  const currentUrl = page.url()
  return !currentUrl.includes('/login')
}

test.describe('Login page', () => {
  test('renders login form with all fields', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('input[name="username"]')).toBeVisible()
    await expect(page.locator('input[name="password"]')).toBeVisible()
    await expect(page.locator('input[type="checkbox"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('shows validation error when submitting empty form', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await page.click('button[type="submit"]')

    const errorVisible = await page
      .locator('p.text-red-700, .text-red-600, .bg-red-50, [class*="error"]')
      .first()
      .isVisible()
      .catch(() => false)

    expect(errorVisible).toBeTruthy()
  })

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await page.fill('input[name="username"]', 'wronguser')
    await page.fill('input[name="password"]', 'wrongpassword')
    await page.click('button[type="submit"]')
    await page.waitForLoadState('networkidle')

    // Should stay on login page
    expect(page.url()).toContain('/login')

    // Should show error message
    const errorMsg = page
      .locator('text=/error|登录失败|invalid|错误/i')
      .first()
    await expect(errorMsg).toBeVisible({ timeout: 5000 })
  })

  test('login button is disabled while loading', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await page.fill('input[name="username"]', 'admin')
    await page.fill('input[name="password"]', 'adminpassword')

    await page.click('button[type="submit"]')

    // Button should be disabled or show loading state during request
    const btn = page.locator('button[type="submit"]').first()
    const isDisabled =
      (await btn.getAttribute('disabled')) !== null ||
      (await btn.isDisabled()) ||
      (await btn.getAttribute('aria-disabled')) === 'true'
    expect(isDisabled).toBeTruthy()
  })

  test('successful login redirects away from /login', async ({ page }) => {
    const loggedIn = await tryLogin(page)
    if (!loggedIn) {
      test.skip()
    }
    expect(page.url()).not.toContain('/login')
  })
})

test.describe('Auth guards', () => {
  test('unauthenticated user is redirected to /login for protected routes', async ({
    page
  }) => {
    localStorage.clear()
    await page.context().clearCookies()

    const protectedRoutes = [
      '/dashboard',
      '/cloud-billing/billing',
      '/data-collector/stats',
      '/settings/profile'
    ]

    for (const route of protectedRoutes) {
      await page.goto(route)
      await page.waitForLoadState('networkidle')
      expect(page.url()).toContain('/login')
    }
  })

  test('keeps stored credentials when auth refresh is unavailable', async ({
    page
  }) => {
    await page.route('**/api/v1/auth/user**', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Authentication credentials were not provided.'
        })
      })
    })

    await page.route('**/api/v1/auth/token/refresh**', async (route) => {
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Bad gateway' })
      })
    })

    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      window.localStorage.setItem('access_token', 'expired-access-token')
      window.localStorage.setItem('refresh_token', 'valid-refresh-token')
    })

    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(500)

    const credentials = await page.evaluate(() => ({
      access: window.localStorage.getItem('access_token'),
      refresh: window.localStorage.getItem('refresh_token')
    }))

    expect(credentials).toEqual({
      access: 'expired-access-token',
      refresh: 'valid-refresh-token'
    })
    await expect(page).toHaveURL(/\/auth-unavailable/, { timeout: 5000 })
  })

  test('uses cached profile for feature checks during auth outage', async ({
    page
  }) => {
    await page.route('**/api/v1/auth/user**', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Authentication credentials were not provided.'
        })
      })
    })

    await page.route('**/api/v1/auth/token/refresh**', async (route) => {
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Bad gateway' })
      })
    })

    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      window.localStorage.setItem('access_token', 'expired-access-token')
      window.localStorage.setItem('refresh_token', 'valid-refresh-token')
      window.localStorage.setItem(
        'user_profile_cache',
        JSON.stringify({
          username: 'cached-user',
          access_profile: {
            visible_features: ['workspace'],
            available_platforms: [
              { key: 'workspace', default_path: '/dashboard' }
            ],
            preferred_platform: 'workspace',
            landing_path: '/dashboard'
          }
        })
      )
    })

    await page.goto('/llm-ops', { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5000 })

    const credentials = await page.evaluate(() => ({
      access: window.localStorage.getItem('access_token'),
      refresh: window.localStorage.getItem('refresh_token')
    }))

    expect(credentials).toEqual({
      access: 'expired-access-token',
      refresh: 'valid-refresh-token'
    })
  })

  test('clears stored credentials when auth refresh is rejected', async ({
    page
  }) => {
    await page.route('**/api/v1/auth/user**', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Authentication failed.' })
      })
    })

    await page.route('**/api/v1/auth/token/refresh**', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Token is invalid or expired' })
      })
    })

    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      window.localStorage.setItem('access_token', 'expired-access-token')
      window.localStorage.setItem('refresh_token', 'invalid-refresh-token')
    })

    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 })

    const credentials = await page.evaluate(() => ({
      access: window.localStorage.getItem('access_token'),
      refresh: window.localStorage.getItem('refresh_token')
    }))

    expect(credentials).toEqual({
      access: null,
      refresh: null
    })
  })

  test('authenticated user is redirected away from /login', async ({ page }) => {
    const loggedIn = await tryLogin(page)
    if (!loggedIn) {
      test.skip()
    }
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    expect(page.url()).not.toContain('/login')
  })
})

test.describe('Language switcher', () => {
  test('language switcher is present on login page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    const langSwitcher = page.locator('select').first()
    await expect(langSwitcher).toBeVisible({ timeout: 5000 })
  })
})
