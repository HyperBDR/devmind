import { test, expect } from '@playwright/test'

test('select remains usable near the bottom of a scrolled dialog', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 500 })
  const module = await page.request.get('/src/components/agione-demo/AgioneSelect.vue')
  test.skip(!module.headers()['content-type']?.includes('javascript'), 'Requires the Vite development server')
  await page.goto('/agione')
  await page.evaluate(async () => {
    const { createApp, h, ref } = await import('/node_modules/.vite/deps/vue.js')
    const { default: Select } = await import('/src/components/agione-demo/AgioneSelect.vue')
    const dialog = document.createElement('dialog')
    dialog.style.cssText = 'height:310px; overflow:hidden;'
    dialog.innerHTML = '<div id="select-test" style="height:260px;overflow:auto"><div style="height:210px"></div><div id="select-mount"></div><div style="height:20px"></div></div>'
    document.body.append(dialog)
    const value = ref('')
    createApp({ render: () => h(Select, {
      label: '测试渠道', modelValue: value.value,
      'onUpdate:modelValue': selected => { value.value = selected },
      options: Array.from({ length: 12 }, (_, i) => ({ label: `渠道 ${i + 1}`, value: String(i) }))
    }) }).mount(dialog.querySelector('#select-mount'))
    dialog.showModal()
    dialog.querySelector('#select-test').scrollTop = 1000
  })
  await page.getByRole('button', { name: '测试渠道' }).click()
  const option = page.getByRole('option', { name: '渠道 1', exact: true })
  await expect(option).toBeVisible()
  await option.click()
  await expect(page.getByRole('button', { name: '测试渠道' })).toContainText('渠道 1')
  await page.getByRole('button', { name: '测试渠道' }).click()
  await page.getByRole('option', { name: '渠道 12', exact: true }).click()
  await expect(page.getByRole('button', { name: '测试渠道' })).toContainText('渠道 12')
  await page.getByRole('button', { name: '测试渠道' }).focus()
  await page.keyboard.press('Enter')
  await page.keyboard.press('Home')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: '测试渠道' })).toContainText('渠道 1')
})
