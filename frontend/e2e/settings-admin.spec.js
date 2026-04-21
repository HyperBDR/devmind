/**
 * E2E tests for Settings pages and Admin (Management) pages.
 * Settings: Profile, Jira, GitLab, LLM, Feishu, Notifications, GlobalSettings
 * Admin: Users, Groups, Roles, LLM sub-pages, TaskManagement, Notifier
 * Requires authenticated user with appropriate features.
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

// ─── Settings pages ────────────────────────────────────────────────────────────

test.describe('Settings - Profile', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Profile page loads and shows profile form', async ({ page }) => {
    await page.goto('/settings/profile')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings\/profile/)

    const title = page.locator('h2').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    const profileForm = page.locator('form, input[name], button').first()
    await expect(profileForm).toBeVisible({ timeout: 10000 })
  })

  test('Profile page has save button', async ({ page }) => {
    await page.goto('/settings/profile')
    await page.waitForLoadState('networkidle')

    const saveBtn = page.locator('button', { hasText: /save|保存|update|更新/i }).first()
    await expect(saveBtn).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Settings - Jira', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Jira settings page loads', async ({ page }) => {
    await page.goto('/settings/jira')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings\/jira/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Settings - GitLab', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('GitLab settings page loads', async ({ page }) => {
    await page.goto('/settings/gitlab')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings\/gitlab/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Settings - LLM', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('LLM settings page loads', async ({ page }) => {
    await page.goto('/settings/llm')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings\/llm/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Settings - Feishu', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Feishu settings page loads', async ({ page }) => {
    await page.goto('/settings/feishu')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings\/feishu/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Settings - Notifications', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Notifications settings page loads', async ({ page }) => {
    await page.goto('/settings/notifications')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings\/notifications/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Settings - Global Settings (Admin)', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Global Settings page loads', async ({ page }) => {
    await page.goto('/admin/global-settings')
    await page.waitForLoadState('networkidle')
    const url = page.url()
    // Either loads the page or redirects to a landing path if not admin
    expect(url).toMatch(/\/(admin\/global-settings|dashboard|login)/)
  })
})

// ─── Admin / Management pages ─────────────────────────────────────────────────

test.describe('Admin - Management Users', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Users management page loads', async ({ page }) => {
    await page.goto('/management/users')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/users/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('Users page shows table or empty state', async ({ page }) => {
    await page.goto('/management/users')
    await page.waitForLoadState('networkidle')
    const tableOrEmpty = page
      .locator('table, text=/暂无|no users/i')
      .first()
    await expect(tableOrEmpty).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Admin - Management Groups', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Groups page loads', async ({ page }) => {
    await page.goto('/management/groups')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/groups/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Admin - Management Roles', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Roles page loads', async ({ page }) => {
    await page.goto('/management/roles')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/roles/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Admin - LLM Management', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('LLM Stats admin page loads', async ({ page }) => {
    await page.goto('/management/llm/stats')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/llm\/stats/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('LLM Usage admin page loads', async ({ page }) => {
    await page.goto('/management/llm/usage')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/llm\/usage/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('LLM Config admin page loads', async ({ page }) => {
    await page.goto('/management/llm/config')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/llm\/config/)
    await expect(page.locator('h1, h2, form').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Admin - Task Management', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Task Management List loads', async ({ page }) => {
    await page.goto('/management/task-management/list')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/task-management\/list/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('Task Management Stats loads', async ({ page }) => {
    await page.goto('/management/task-management/stats')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/task-management\/stats/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('Task Management Settings loads', async ({ page }) => {
    await page.goto('/management/task-management/settings')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/task-management\/settings/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Admin - Notifier', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('Notifier Stats page loads', async ({ page }) => {
    await page.goto('/management/notifier/stats')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/notifier\/stats/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('Notifier Records page loads', async ({ page }) => {
    await page.goto('/management/notifier/records')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/notifier\/records/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('Notifier Channels page loads', async ({ page }) => {
    await page.goto('/management/notifier/channels')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/notifier\/channels/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('Notifier Settings page loads', async ({ page }) => {
    await page.goto('/management/notifier/settings')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/management\/notifier\/settings/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

// ─── Redirect / legacy routes ──────────────────────────────────────────────────

test.describe('Legacy LLM routes redirect to management', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('/llm/* redirects to /management/llm/*', async ({ page }) => {
    await page.goto('/llm/stats')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/management\/llm\/stats/)
  })

  test('/task-management/* redirects to /management/task-management/*', async ({ page }) => {
    await page.goto('/task-management/list')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/management\/task-management\/list/)
  })

  test('/notifier/* redirects to /management/notifier/*', async ({ page }) => {
    await page.goto('/notifier/stats')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/management\/notifier\/stats/)
  })
})
