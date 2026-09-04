import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const create = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const preview = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationPreview.vue',
    import.meta.url,
  ),
  'utf8',
)
const api = readFileSync(
  new URL('../src/modules/quotation/api/quotations.ts', import.meta.url),
  'utf8',
)
const totals = readFileSync(
  new URL(
    '../src/modules/quotation/utils/quotationTotals.ts',
    import.meta.url,
  ),
  'utf8',
)
const en = readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
)
const zh = readFileSync(
  new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
  'utf8',
)

test('tax direction defaults to add and supports subtraction', () => {
  assert.match(create, /ref<TaxCalculation>\('add'\)/)
  assert.match(create, /taxCalculation = 'subtract'/)
  assert.match(totals, /taxCalculation === 'subtract'/)
  assert.match(preview, /taxCalculation === 'subtract' \? '-' : ''/)
  assert.match(api, /tax_calculation: quote\.taxCalculation \|\| 'add'/)
  assert.match(create, /taxAdjustmentAddSummary/)
  assert.match(create, /taxAdjustmentSubtractSummary/)
  assert.match(en, /"taxAdjustmentAddSummary": "Added to Grand Total"/)
  assert.match(zh, /"taxAdjustmentSubtractSummary": "从 Grand Total 扣减"/)
})

test('additional total uses the approved integrated field widths', () => {
  assert.match(
    create,
    /grid-cols-\[minmax\(0,1fr\)_88px_120px\]/,
  )
  assert.match(create, /quote-additional-total-label/)
  assert.match(create, /quote-additional-total-currency/)
  assert.match(create, /quote-additional-total-amount/)
  assert.match(create, /additionalCurrencyOptions/)
  assert.match(create, /MYR', label: 'MYR \(RM\)'/)
  assert.match(create, /HKD', label: 'HKD \(HK\$\)'/)
  assert.match(preview, /model\.additionalGrandTotalLabel/)
  assert.match(api, /additional_grand_total_amount:/)
})

test('additional total heading does not duplicate the editable default label', () => {
  assert.match(en, /"additionalGrandTotal": "Additional"/)
  assert.match(zh, /"additionalGrandTotal": "附加"/)
})

test('long tax labels do not squeeze the rate field at normal widths', () => {
  assert.match(
    create,
    /grid gap-3 2xl:grid-cols-\[minmax\(0,1\.25fr\)_minmax\(180px,0\.75fr\)\]/,
  )
})
