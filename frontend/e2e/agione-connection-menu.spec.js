import { test, expect } from '@playwright/test'

test('connection menu stays above workspace and scrolls on a laptop', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 })
  const module = await page.request.get('/src/pages/AgioneOps.vue')
  test.skip(!module.headers()['content-type']?.includes('javascript'), 'Requires the Vite development server')
  await page.route('**/api/v1/**', route => route.fulfill({ status: 403, body: '{}' }))
  await page.goto('/agione')
  await page.evaluate(async () => {
    const { createApp, h } = await import('/node_modules/.vite/deps/vue.js')
    const { createPinia } = await import('/node_modules/.vite/deps/pinia.js')
    const { createI18n } = await import('/node_modules/.vite/deps/vue-i18n.js')
    const source = await (await fetch('/src/components/layout/PlatformSwitcher.vue')).text()
    const routerPath = source.match(/from "(\/node_modules\/\.vite\/deps\/vue-router\.js[^"]*)"/)[1]
    const { createRouter, createMemoryHistory } = await import(routerPath)
    const { default: Page } = await import('/src/pages/AgioneOps.vue')
    document.body.innerHTML = '<div id="menu-test"></div>'
    const app = createApp({ render: () => h(Page) })
    app.use(createPinia())
    app.use(createRouter({ history: createMemoryHistory(), routes: [] }))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': {} } }))
    app.mount('#menu-test')
    const workspace = document.querySelector('#menu-test .workspace')
    const panel = document.createElement('div')
    panel.style.cssText = 'position:fixed;z-index:1;left:210px;top:0;right:0;bottom:0;background:white'
    workspace.append(panel)
  })
  await page.locator('#menu-test .sidebar-connection-trigger').click()
  const menu = page.locator('#menu-test .sidebar-connection-menu')
  await expect(menu).toBeVisible()
  await menu.evaluate(element => {
    for (let i = 0; i < 20; i++) {
      const row = document.createElement('button')
      row.textContent = `测试连接 ${i + 1}`
      row.setAttribute('role', 'menuitemradio')
      element.append(row)
    }
  })
  const bounds = await menu.evaluate(element => {
    const rect = element.getBoundingClientRect()
    return {
      top: rect.top,
      bottom: rect.bottom,
      scrollable: element.scrollHeight > element.clientHeight,
      onTop: element.contains(document.elementFromPoint(rect.right - 5, rect.top + 20))
    }
  })
  expect(bounds.top).toBeGreaterThanOrEqual(0)
  expect(bounds.bottom).toBeLessThanOrEqual(600)
  expect(bounds.scrollable).toBe(true)
  expect(bounds.onTop).toBe(true)
  const last = menu.getByRole('menuitemradio', { name: '测试连接 20' })
  await last.scrollIntoViewIfNeeded()
  await expect(last).toBeVisible()
  await last.focus()
  await page.keyboard.press('Escape')
  await expect(menu).toBeHidden()
})
