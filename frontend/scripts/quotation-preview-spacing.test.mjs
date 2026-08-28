import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(
  new URL('../src/modules/quotation/components/QuotationPreview.vue', import.meta.url),
  'utf8',
)
const modelSource = fs.readFileSync(
  new URL('../src/modules/quotation/utils/quotationPreviewModel.ts', import.meta.url),
  'utf8',
)
const notesBlock = source.split('Additional Notes & Disclaimers:')[1]
const spacing = notesBlock.split('To indicate Customer acceptance')[0]

assert.equal((spacing.match(/<tr class="h-3">/g) || []).length, 2)

const quotationStart = source.indexOf('Quotation\n')
const dateStart = source.indexOf('Date:')
const quotationSpacing = source.slice(quotationStart, dateStart)
assert.equal((quotationSpacing.match(/<tr class="h-5">/g) || []).length, 2)

const billingEnd = source.indexOf('Bill to:')
const contactStart = source.indexOf('Contact Person')
const contactSpacing = source.slice(billingEnd, contactStart)
assert.equal((contactSpacing.match(/<tr class="h-4">/g) || []).length, 2)

const totalsStart = source.indexOf('Grand Total:')
const additionalStart = source.indexOf('Additional Notes & Disclaimers:')
const additionalSpacing = source.slice(totalsStart, additionalStart)
assert.equal((additionalSpacing.match(/<tr class="h-3">/g) || []).length, 2)

assert.match(modelSource, /softwareRows: fitTemplateRows\(softwareItems, 1, 'Software'\)/)
assert.match(modelSource, /othersRows: fitTemplateRows\(othersItems, 1, 'Other'\)/)
