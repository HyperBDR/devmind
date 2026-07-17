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

test.describe('Quotation desktop experience', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  const pages = [
    ['/quotation/dashboard', 'Quote Breakdown'],
    ['/quotation/list', 'Quotes'],
    ['/quotation/create', 'New Quote'],
    ['/quotation/imports', 'Import Queue'],
    ['/quotation/catalog', 'Catalog']
  ]

  for (const [path, heading] of pages) {
    test(`${heading} renders without desktop overflow`, async ({ page }) => {
      await page.goto(path)
      await expect(page.getByText(heading, { exact: true }).first()).toBeVisible()

      const layout = await page.evaluate(() => {
        const root = document.documentElement
        const clippedControls = [
          ...document.querySelectorAll('button, h1, h2, h3, h4, label, th')
        ]
          .filter((element) => {
            const rect = element.getBoundingClientRect()
            return (
              rect.width > 0 &&
              rect.height > 0 &&
              (element.scrollWidth > element.clientWidth + 1 ||
                element.scrollHeight > element.clientHeight + 1)
            )
          })
          .map((element) => (element.textContent || '').trim())
          .filter(Boolean)

        return {
          pageOverflow: root.scrollWidth > root.clientWidth + 1,
          clippedControls
        }
      })

      expect(layout.pageOverflow).toBe(false)
      expect(layout.clippedControls).toEqual([])
    })
  }

  test('sidebar links expose the complete quote workflow', async ({ page }) => {
    await page.goto('/quotation/dashboard')

    await expect(page.getByRole('link', { name: 'Overview' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Quotes' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'New Quote' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Import Queue' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Catalog' })).toBeVisible()
  })

  test('platform switch opens Quote Desk without an embedded sign-in error', async ({
    page
  }) => {
    await page.goto('/dashboard')
    await page.evaluate(() => {
      window.__quotationSignInErrorSeen = false
      const observer = new MutationObserver(() => {
        if (document.body.innerText.includes("Couldn't sign in automatically")) {
          window.__quotationSignInErrorSeen = true
        }
      })
      observer.observe(document.body, { childList: true, subtree: true })
    })
    await page.getByRole('button', { name: /Workspace|Quote Desk/ }).click()
    await page.getByRole('link', { name: 'Quote Desk' }).click()

    await expect(page).toHaveURL(/\/quotation\/dashboard/)
    await expect(page.getByText('Quote Breakdown', { exact: true })).toBeVisible()
    await expect(
      page.getByText("Couldn't sign in automatically", { exact: true })
    ).toHaveCount(0)
    expect(await page.evaluate(() => window.__quotationSignInErrorSeen)).toBe(
      false
    )
  })
})
