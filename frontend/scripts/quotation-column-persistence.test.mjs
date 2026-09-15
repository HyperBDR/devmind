import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const quoteList = readFileSync(
  new URL('../src/modules/quotation/components/QuotationList.vue', import.meta.url),
  'utf8',
)
const invoiceList = readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/InvoiceList.vue',
    import.meta.url,
  ),
  'utf8',
)

test('Quote and Invoice columns use separate persisted preferences', () => {
  assert.match(quoteList, /loadVisibleColumns\(\s*'quote'/)
  assert.match(quoteList, /saveVisibleColumns\('quote'/)
  assert.match(invoiceList, /loadVisibleColumns\(\s*'invoice'/)
  assert.match(invoiceList, /saveVisibleColumns\('invoice'/)
})

test('Invoice list omits due date and exposes document type', () => {
  assert.doesNotMatch(invoiceList, /dueDate:/)
  assert.doesNotMatch(invoiceList, /columnIsVisible\('dueDate'\)/)
  assert.match(invoiceList, /documentKind:/)
})

test('Invoice list exposes parsed customer contact names', () => {
  assert.match(invoiceList, /customerContactPerson:/)
  assert.match(invoiceList, /columnIsVisible\('customerContactPerson'\)/)
  assert.match(invoiceList, /invoice\.customer_contact_person/)
  assert.equal(
    JSON.parse(
      readFileSync(
        new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
        'utf8',
      ),
    ).quotation.sales.fields.customerContactPerson,
    '客户联系人',
  )
})
