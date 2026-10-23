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
const spacing = notesBlock.split('QuotationAcceptanceRows')[0]

assert.equal((spacing.match(/class="h-\[10px\]"/g) || []).length, 2)
assert.doesNotMatch(source, /wrapQuotationDisclaimer/)
assert.match(source, /\{\{ model\.remarksDisclaimer \}\}/)

const quotationStart = source.indexOf('Quotation\n')
const dateStart = source.indexOf('Date:')
const quotationSpacing = source.slice(quotationStart, dateStart)
assert.equal((quotationSpacing.match(/<tr class="h-\[13px\]">/g) || []).length, 2)

const billingEnd = source.indexOf('Bill to:')
const contactStart = source.indexOf('Contact Person')
const contactSpacing = source.slice(billingEnd, contactStart)
assert.equal((contactSpacing.match(/<tr class="h-\[10px\]">/g) || []).length, 2)

const additionalStart = source.indexOf('Additional Notes & Disclaimers:')
const totalsStart = source.lastIndexOf('Grand Total:', additionalStart)
const additionalSpacing = source.slice(totalsStart, additionalStart)
assert.equal((additionalSpacing.match(/<tr class="h-\[8px\]">/g) || []).length, 2)

assert.match(source, /props\.scale === 'compact' \? '986px' : '1020px'/)
assert.match(source, /'pl-\[63px\] pr-\[70px\] py-\[84px\]'/)
assert.match(source, /paginateQuotation\(source\.value, staging/)
assert.match(source, /signatureTop: props\.scale === 'compact' \? 79 : 81/)
assert.match(source, /continuationTop: props\.scale === 'compact' \? 84 : 87/)
assert.match(source, /minHeight: previewFrameMinHeight/)
assert.doesNotMatch(source, /iframe|quotation-preview-pdf|previewPdf/)

assert.match(modelSource, /softwareRows: fitTemplateRows\(softwareItems, 1, 'Software'\)/)
assert.match(modelSource, /othersRows: fitTemplateRows\(othersItems, 1, 'Other'\)/)
