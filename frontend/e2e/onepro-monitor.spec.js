import { test, expect } from '@playwright/test'

const routes = [
  '/onepro-monitor/dashboard',
  '/onepro-monitor/tenants',
  '/onepro-monitor/licenses',
  '/onepro-monitor/hosts',
  '/onepro-monitor/tasks',
  '/onepro-monitor/settings/data-sources',
  '/onepro-monitor/settings/system'
]

test.describe('OnePro Monitor routes', () => {
  for (const route of routes) {
    test(`route ${route} is reachable or redirected to login`, async ({
      page
    }) => {
      await page.goto(route)
      await page.waitForLoadState('networkidle')

      const url = page.url()
      expect(url).toMatch(/\/(login|onepro-monitor\/.*)(\?|$)/)
    })
  }
})
