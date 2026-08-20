import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(
  new URL('../src/modules/quotation/components/QuotationPreview.vue', import.meta.url),
  'utf8',
)
const notesBlock = source.split('Additional Notes & Disclaimers:')[1]
const spacing = notesBlock.split('To indicate Customer acceptance')[0]

assert.equal((spacing.match(/<tr class="h-3">/g) || []).length, 2)
