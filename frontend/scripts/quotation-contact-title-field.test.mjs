import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(
  new URL('../src/modules/quotation/components/QuotationCreate.vue', import.meta.url),
  'utf8',
)

assert.match(source, /issuerContactTitle/)
assert.match(source, /quotation\.pages\.create\.issuerContactTitle/)
assert.match(source, /v-model="issuerContactTitle"/)
