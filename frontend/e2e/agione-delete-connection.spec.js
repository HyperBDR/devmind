import { test, expect } from '@playwright/test'

test('connection deletion requires confirmation and prevents duplicate submits', async ({ page }) => {
  const module = await page.request.get('/src/components/agione-demo/DeleteConnectionDialog.vue')
  test.skip(!module.headers()['content-type']?.includes('javascript'), 'Requires the Vite development server')
  await page.goto('/agione')
  await page.evaluate(async () => {
    const { createApp, h, ref } = await import('/node_modules/.vite/deps/vue.js')
    const { default: Dialog } = await import('/src/components/agione-demo/DeleteConnectionDialog.vue')
    const host = document.createElement('div')
    document.body.append(host)
    const busy = ref(false)
    const component = ref(null)
    window.deleteTestSubmits = 0
    createApp({ render: () => h(Dialog, {
      ref: component, connectionName: 'AGIOne Pro · Provider',
      description: '密钥将被清除；历史数据和通知规则会保留。',
      busy: busy.value,
      onConfirm: () => { window.deleteTestSubmits++; busy.value = true }
    }) }).mount(host)
    component.value.open()
  })
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('AGIOne Pro · Provider')
  await expect(dialog).toContainText('历史数据和通知规则会保留')
  expect(await page.evaluate(() => window.deleteTestSubmits)).toBe(0)
  await dialog.getByRole('button', { name: '确认删除' }).click()
  await expect(dialog.getByRole('button', { name: '正在删除…' })).toBeDisabled()
  expect(await page.evaluate(() => window.deleteTestSubmits)).toBe(1)
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
})
