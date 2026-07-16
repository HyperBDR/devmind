import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const model = readFileSync(
  new URL('../src/modules/quotation/utils/quotationPreviewModel.ts', import.meta.url),
  'utf8',
)
const excel = readFileSync(
  new URL('../src/modules/quotation/utils/excelGenerator.ts', import.meta.url),
  'utf8',
)
const pdf = readFileSync(
  new URL('../src/modules/quotation/utils/pdfExporter.ts', import.meta.url),
  'utf8',
)

test('template row padding never truncates real quotation line items', () => {
  assert.match(model, /length: Math\.max\(count, items\.length\)/)
  assert.match(excel, /model\.softwareRows/)
  assert.match(excel, /model\.othersRows/)
  assert.match(pdf, /renderLineRows\(model\.softwareRows\)/)
  assert.match(pdf, /renderLineRows\(model\.othersRows\)/)
  assert.match(excel, /function lineItemRowHeight\(description: string\)/)
  assert.match(excel, /this\.nextRow\(lineItemRowHeight\(rowDescription\(item\)\)\)/)
})
