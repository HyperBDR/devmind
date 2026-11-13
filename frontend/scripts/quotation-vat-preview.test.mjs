import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'

let vite
let Preview
let mapApiQuotation

before(async () => {
  vite = await createServer({
    configFile: 'vite.config.js',
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'error',
  })
  Preview = (await vite.ssrLoadModule(
    '/src/modules/quotation/components/QuotationPreview.vue',
  )).default
  ;({ mapApiQuotation } = await vite.ssrLoadModule(
    '/src/modules/quotation/api/quotations.ts',
  ))
})

after(async () => { await vite?.close() })

const base = {
  id: 'quote-1', quote_no: 'Q-1', status: 'draft', version_current: 0,
  source_type: 'manual', product_line: 'BDR', project_name: 'Example',
  currency: 'USD', payment_term_option: 'CIA', payment_terms: 'CIA',
  quote_date: '2026-11-13', expire_date: '2026-12-13', tax_label: 'VAT',
  vat_rate: '0.00', vat_amount: '0.00', deduction_amount: '0.00',
  software_subtotal: '100.00', others_subtotal: '0.00',
  subtotal_before_vat: '100.00', grand_total: '100.00',
  issuer_company_name: 'Example', issuer_contact_name: 'Alice',
  issuer_contact_email: 'a@example.com', issuer_contact_title: '',
  client_company: 'Client', contact_person: 'Bob', email: 'b@example.com',
  billing_company: 'Client', billing_contact: 'Bob', billing_email: 'b@example.com',
  created_at: '2026-11-13T00:00:00Z', updated_at: '2026-11-13T00:00:00Z',
  items: [],
}

async function render(quote) {
  const app = createSSRApp({ render: () => h(Preview, { quote }) })
  app.use(createI18n({ legacy: false, locale: 'en', messages: { en: {} },
    missingWarn: false, fallbackWarn: false }))
  return renderToString(app)
}

test('saved new quotes hide zero VAT subtotal and keep nonzero VAT subtotal', async () => {
  for (const [rate, visible] of [['0.00', false], ['0.01', true]]) {
    const quote = mapApiQuotation({ ...base, vat_rate: rate,
      hide_zero_vat_subtotal: true })
    assert.equal((await render(quote)).includes('Subtotal before VAT:'), visible)
  }
})

test('saved legacy quotes retain their zero VAT subtotal', async () => {
  for (const flag of [undefined, false]) {
    const quote = mapApiQuotation({ ...base, hide_zero_vat_subtotal: flag })
    assert.match(await render(quote), /Subtotal before VAT:/)
  }
})
