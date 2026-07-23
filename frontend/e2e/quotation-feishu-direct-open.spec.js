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

test('imported Feishu file opens the trusted Feishu page directly', async ({
  page,
  context,
}) => {
  await login(page)
  let accessRecorded = false
  let proxyContentRequested = false

  await context.route('https://tenant.feishu.cn/**', async (route) => {
    await route.fulfill({
      contentType: 'text/html',
      body: '<h1>Feishu permission page</h1>',
    })
  })
  await page.route('**/api/v1/quotation/feishu/sync-folder', async (route) => {
    await route.fulfill({
      json: {
        created_count: 0,
        skipped_count: 1,
        errors: [],
        folders: [],
        file_locations: [],
      },
    })
  })
  await page.route('**/api/v1/quotation/documents?source=feishu', async (route) => {
    await route.fulfill({
      json: [
        {
          id: 'imported-document-id',
          quotation_id: null,
          doc_type: 'pdf',
          file_name: 'Imported quotation.pdf',
          mime_type: 'application/pdf',
          size_bytes: 2048,
          source: 'feishu',
          feishu_file_token: null,
          feishu_url: 'https://tenant.feishu.cn/file/imported_token',
          feishu_folder_path: [
            { token: 'archive-root', name: 'Quotation archive' },
          ],
          remote_access_available: true,
          created_by_email: 'admin@example.com',
          created_at: '2026-07-21T01:00:00Z',
        },
      ],
    })
  })
  await page.route(
    '**/api/v1/quotation/feishu/documents/imported-document-id/access',
    async (route) => {
      accessRecorded = true
      await route.fulfill({
        json: {
          exists: true,
          document_id: 'imported-document-id',
          direct_access_allowed: true,
          url: 'https://tenant.feishu.cn/file/imported_token',
        },
      })
    },
  )
  page.on('request', (request) => {
    if (request.url().includes('/content')) proxyContentRequested = true
  })

  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/quotation/list')
  await expect(page.getByText('Imported quotation.pdf')).toBeVisible()
  const openButton = page.getByTitle('Open in Feishu')
  await expect(openButton).toBeVisible()
  await openButton.scrollIntoViewIfNeeded()
  await page.screenshot({ path: '/tmp/devmind-feishu-direct-open-button.png' })

  const popupPromise = page.waitForEvent('popup')
  await openButton.click()
  const popup = await popupPromise
  await expect(popup).toHaveURL(
    'https://tenant.feishu.cn/file/imported_token',
  )
  await expect(popup.getByRole('heading', { name: 'Feishu permission page' })).toBeVisible()
  await expect.poll(() => accessRecorded).toBe(true)
  expect(proxyContentRequested).toBe(false)

  const pageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(pageOverflow).toBe(false)
  await popup.close()
})
