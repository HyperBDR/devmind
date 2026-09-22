import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

globalThis.localStorage = { getItem: () => 'en' }

const {
  extractQuoteDeskErrorDetail,
  quoteDeskErrorMessage,
} = await import('../src/utils/quoteDeskErrors.js')
const quotationClient = fs.readFileSync(
  new URL('../src/modules/quotation/api/client.ts', import.meta.url),
  'utf8',
)

test('formats serializer field errors for duplicate numbers', () => {
  const detail = extractQuoteDeskErrorDetail({
    invoice_no: ['Invoice number already exists.'],
  })

  assert.match(detail, /invoice_no/)
  assert.equal(
    quoteDeskErrorMessage(400, '/api/v1/quotation/invoices', detail),
    'This number is already in use. Please enter a unique number.',
  )
})

test('apiRequest formats serializer field errors before fallback text', () => {
  const detail = extractQuoteDeskErrorDetail({
    quote_no: ['Quote number already exists.'],
  })

  assert.match(
    quotationClient,
    /extractQuoteDeskErrorDetail\(unwrapped \?\? payload\)/,
  )
  assert.equal(
    quoteDeskErrorMessage(400, '/api/v1/quotation/quotations', detail),
    'This number is already in use. Please enter a unique number.',
  )
})
