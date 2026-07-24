import { expect, test } from '@playwright/test'

const mobileViewports = [
  { width: 320, height: 700 },
  { width: 390, height: 844 },
  { width: 768, height: 900 },
  { width: 1023, height: 900 },
  { width: 844, height: 390 }
]
const llmOpsPlatform = {
  key: 'llm_ops',
  default_path: '/llm-ops'
}

async function setupAuthenticatedSession(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'e2e-token')
    window.localStorage.setItem('userLanguage', 'en')
  })

  await page.route('**/api/v1/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname

    if (pathname.endsWith('/api/v1/auth/user')) {
      await route.fulfill({
        json: {
          id: 1,
          username: 'admin',
          access_profile: {
            visible_features: ['llm_ops'],
            available_platforms: [llmOpsPlatform],
            landing_path: '/llm-ops'
          }
        }
      })
      return
    }

    if (pathname.endsWith('/api/v1/llm-ops/summary/')) {
      await route.fulfill({
        json: {
          currency: {
            display_currency: 'CNY',
            usd_to_cny_rate: 7.15
          }
        }
      })
      return
    }

    await route.fulfill({ json: { count: 0, results: [] } })
  })
}

async function openLLMOps(page, viewport) {
  await page.setViewportSize(viewport)
  await setupAuthenticatedSession(page)
  await page.goto('/llm-ops', { waitUntil: 'domcontentloaded' })
  await expect(
    page.getByRole('heading', { name: 'Operations Overview' })
  ).toBeVisible()
}

for (const viewport of mobileViewports) {
  test(`compact drawer at ${viewport.width}x${viewport.height}`, async ({
    page
  }) => {
    await openLLMOps(page, viewport)

    const openButton = page.getByRole('button', {
      name: 'Open navigation'
    })
    await expect(openButton).toBeVisible()
    await expect(
      page.getByRole('dialog', { name: 'LLM Operations navigation' })
    ).toHaveCount(0)

    const layout = await page.evaluate(() => {
      const title = document.querySelector('.page-hero-title')
      return {
        overflow: document.documentElement.scrollWidth > window.innerWidth,
        titleTop: title?.getBoundingClientRect().top ?? Infinity
      }
    })

    expect(layout.overflow).toBe(false)
    expect(layout.titleTop).toBeLessThan(Math.min(viewport.height, 260))

    const buttonBox = await openButton.boundingBox()
    expect(buttonBox?.height).toBeGreaterThanOrEqual(44)
  })
}

test('closes the drawer and restores trigger focus', async ({ page }) => {
  await openLLMOps(page, { width: 390, height: 844 })

  const openButton = page.getByRole('button', { name: 'Open navigation' })
  await openButton.click()

  const dialog = page.getByRole('dialog', {
    name: 'LLM Operations navigation'
  })
  await expect(dialog).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Close navigation' })
  ).toBeFocused()

  await page.getByRole('button', { name: 'Close navigation' }).click()

  await expect(dialog).toHaveCount(0)
  await expect(openButton).toBeFocused()

  await openButton.click()
  await expect(dialog).toBeVisible()

  await page.keyboard.press('Escape')

  await expect(dialog).toHaveCount(0)
  await expect(openButton).toBeFocused()
})

test('closes the drawer from its overlay', async ({ page }) => {
  await openLLMOps(page, { width: 768, height: 900 })

  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(
    page.getByRole('dialog', { name: 'LLM Operations navigation' })
  ).toBeVisible()

  await page
    .getByTestId('llm-ops-mobile-navigation-overlay')
    .click({ position: { x: 700, y: 450 } })

  await expect(
    page.getByRole('dialog', { name: 'LLM Operations navigation' })
  ).toHaveCount(0)
})

test('selects a mobile navigation item and closes the drawer', async ({
  page
}) => {
  await openLLMOps(page, { width: 390, height: 844 })

  await page.getByRole('button', { name: 'Open navigation' }).click()
  const metaModelsButton = page.getByRole('button', { name: 'Meta Models' })
  const buttonBox = await metaModelsButton.boundingBox()
  expect(buttonBox?.height).toBeGreaterThanOrEqual(44)
  await metaModelsButton.click()

  await expect(
    page.getByRole('dialog', { name: 'LLM Operations navigation' })
  ).toHaveCount(0)
  const metaModelsHeading = page.getByRole('heading', { name: 'Meta Models' })
  await expect(metaModelsHeading).toBeVisible()
  await expect(page).toHaveURL(/section=metaModels/)
})

test('keeps the desktop sidebar at 1024px', async ({ page }) => {
  await openLLMOps(page, { width: 1023, height: 900 })

  await page.getByRole('button', { name: 'Open navigation' }).click()
  const dialog = page.getByRole('dialog', {
    name: 'LLM Operations navigation'
  })
  await expect(dialog).toBeVisible()

  await page.setViewportSize({ width: 1024, height: 900 })

  await expect(
    page.getByRole('button', { name: 'Open navigation' })
  ).toBeHidden()
  await expect(dialog).toHaveCount(0)
  await expect(page.locator('.llm-ops-sidebar')).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Collapse sidebar' })
  ).toBeVisible()
})
