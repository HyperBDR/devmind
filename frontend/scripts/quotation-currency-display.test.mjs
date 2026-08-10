import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const previewModel = readFileSync(
  new URL(
    '../src/modules/quotation/utils/quotationPreviewModel.ts',
    import.meta.url
  ),
  'utf8'
)
const quotationList = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationList.vue',
    import.meta.url
  ),
  'utf8'
)
const dashboard = readFileSync(
  new URL(
    '../src/modules/quotation/components/Dashboard.vue',
    import.meta.url
  ),
  'utf8'
)
const quotationCreate = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url
  ),
  'utf8'
)

test('parsed amounts use symbols when available and short labels otherwise', () => {
  assert.match(previewModel, /export function getCurrencySymbol/)
  assert.match(previewModel, /code === 'USD'\) return '\$'/)
  assert.match(previewModel, /code === 'CNY'\) return '¥'/)
  assert.match(previewModel, /code === 'EUR'\) return '€'/)
  assert.match(previewModel, /code === 'GBP'\) return '£'/)
  assert.match(previewModel, /code === 'HKD'\) return 'HK\$'/)
  assert.match(previewModel, /code === 'MYR'\) return 'RM'/)
  assert.match(quotationList, /getCurrencySymbol/)
  assert.match(dashboard, /currencyShortLabel/)
  assert.match(dashboard, /'RM'/)
  assert.match(dashboard, /getCurrencySymbol/)
  assert.match(dashboard, /'GBP'/)
  assert.match(quotationCreate, /getCurrencySymbol\(currency\.value\)/)
})
