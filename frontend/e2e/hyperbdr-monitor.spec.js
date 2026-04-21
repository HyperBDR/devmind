import { test, expect } from '@playwright/test'

const routes = [
  '/hyperbdr-monitor/dashboard',
  '/hyperbdr-monitor/tenants',
  '/hyperbdr-monitor/licenses',
  '/hyperbdr-monitor/hosts',
  '/hyperbdr-monitor/tasks',
  '/hyperbdr-monitor/settings/data-sources',
  '/hyperbdr-monitor/settings/system'
]

test.describe('HyperBDR Monitor routes', () => {
  for (const route of routes) {
    test(`route ${route} is reachable or redirected to login`, async ({
      page
    }) => {
      await page.goto(route)
      await page.waitForLoadState('networkidle')

      const url = page.url()
      expect(url).toMatch(/\/(login|hyperbdr-monitor\/.*)(\?|$)/)
    })
  }
})
