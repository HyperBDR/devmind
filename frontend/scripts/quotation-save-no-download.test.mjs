import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)
const quotationList = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationList.vue',
    import.meta.url,
  ),
  'utf8',
)
const quotationDetails = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationDetails.vue',
    import.meta.url,
  ),
  'utf8',
)
const chinese = JSON.parse(
  readFileSync(
    new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
    'utf8',
  ),
)

test('saving and generating a quote does not download a file', () => {
  const saveStart = app.indexOf('async function handleSaveQuotation')
  const saveEnd = app.indexOf('async function handleFeishuUploadDone')
  const saveFlow = app.slice(saveStart, saveEnd)

  assert.ok(saveStart >= 0)
  assert.ok(saveEnd > saveStart)
  assert.match(saveFlow, /generateQuotationApi/)
  assert.doesNotMatch(saveFlow, /exportQuotationFile/)
  assert.doesNotMatch(saveFlow, /document\.download/)
  assert.equal(chinese.quotation.actions.saveAndGenerate, '保存报价单')
  assert.doesNotMatch(chinese.quotation.app.quoteGenerated, /下载/)
})

test('explicit download controls continue to use the export API', () => {
  assert.match(quotationList, /exportQuotationFile\(quote\.id, exportFormat/)
  assert.match(quotationDetails, /exportQuotationFile\(props\.quote\.id, 'xlsx'/)
  assert.match(quotationDetails, /exportQuotationFile\(props\.quote\.id, 'pdf'/)
})
