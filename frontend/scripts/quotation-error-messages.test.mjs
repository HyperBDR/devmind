import assert from 'node:assert/strict'
import test from 'node:test'

globalThis.localStorage = { getItem: () => 'en' }

const {
  extractQuoteDeskErrorDetail,
  quoteDeskErrorMessage,
} = await import('../src/utils/quoteDeskErrors.js')

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
