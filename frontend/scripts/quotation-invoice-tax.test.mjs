import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createServer } from 'vite'

let vite
let Preview
let calculateInvoiceTotals
before(async () => {
  vite = await createServer({ configFile: 'vite.config.js',
    server: { middlewareMode: true, hmr: false }, appType: 'custom', logLevel: 'error' })
  Preview = (await vite.ssrLoadModule('/src/modules/quotation/components/sales/InvoicePreview.vue')).default
  ;({ calculateInvoiceTotals } = await vite.ssrLoadModule('/src/modules/quotation/utils/invoiceTotals.ts'))
})
after(async () => { await vite?.close() })

const items = [
  { id: '1', description: 'License', quantity: 50, unitPrice: 913.5 },
  { id: '2', description: 'Service', quantity: 50, unitPrice: 232.73 },
]
const invoice = { invoiceNumber: 'INV-1', documentKind: 'invoice',
  invoiceDate: '2026-11-16', currency: 'MYR', items }
const render = (data) => renderToString(createSSRApp({ render: () => h(Preview, { invoice: data }) }))

test('calculates tax per line using decimal half-up rounding', () => {
  assert.deepEqual(calculateInvoiceTotals(items, 8),
    { subtotal: 57311.5, tax: 4584.92, total: 61896.42 })
  assert.deepEqual(calculateInvoiceTotals([
    { quantity: 1, unitPrice: 10.075 },
    { quantity: 1, unitPrice: 0.05 },
  ], 10), { subtotal: 10.13, tax: 1.02, total: 11.15 })
})

test('preview shows tax on new invoices and preserves the old display', async () => {
  const withTax = await render({ ...invoice, taxLabel: 'Digital Service Tax (DST)', taxRate: 8 })
  assert.match(withTax, /Digital Service Tax \(DST\) \(8%\):/)
  assert.match(withTax, /4,584\.92/)
  assert.match(withTax, /61,896\.42/)
  const legacy = await render(invoice)
  assert.doesNotMatch(legacy, /Subtotal before tax:/)
  assert.doesNotMatch(legacy, /Digital Service Tax/)
})
