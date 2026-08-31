import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)
const create = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
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

test(
  'saving a quote refreshes the numbering context for the next quote',
  () => {
    const saveStart = app.indexOf('async function handleSaveQuotation')
    const saveEnd = app.indexOf('async function handleFeishuUploadDone')
    const saveFlow = app.slice(saveStart, saveEnd)

    assert.match(
      saveFlow,
      /await refreshQuotations\(quotationListQuery\.value\)/,
    )
  assert.match(saveFlow, /await loadQuotationFormContext\(\)/)

  assert.match(app, /:existing-quote-numbers="quotationFormContextQuoteNumbers"/)

    const tabStart = app.indexOf('function goTab')
    const tabEnd = app.indexOf('function handleCustomerQuote')
    const tabFlow = app.slice(tabStart, tabEnd)
    assert.match(
      tabFlow,
      /if \(tab === 'create'\) void loadQuotationFormContext\(\)/,
    )
  },
)

test('explicit download controls continue to use the export API', () => {
  assert.match(quotationList, /exportQuotationFile\(quote\.id, exportFormat/)
  assert.match(quotationDetails, /exportQuotationFile\(props\.quote\.id, 'xlsx'/)
  assert.match(quotationDetails, /exportQuotationFile\(props\.quote\.id, 'pdf'/)
})

test('imported quotations do not render the copy action', () => {
  const copyStart = quotationList.indexOf('t(\'quotation.pages.list.copyQuote\')')
  const copyBlock = quotationList.slice(copyStart - 300, copyStart + 300)

  assert.ok(copyStart >= 0)
  assert.match(copyBlock, /v-if="quote\.sourceType !== 'document_import'"/)
})

test('copy opens a create form without creating a quotation first', () => {
  const copyStart = app.indexOf('async function handleCopyQuote')
  const copyEnd = app.indexOf('function handleBackToList')
  const copyFlow = app.slice(copyStart, copyEnd)

  assert.ok(copyStart >= 0)
  assert.ok(copyEnd > copyStart)
  assert.match(copyFlow, /getQuotationApi\(id\)/)
  assert.match(copyFlow, /copySourceQuote\.value = sourceQuote/)
  assert.match(copyFlow, /router\.push\('\/quotation\/create'\)/)
  assert.doesNotMatch(copyFlow, /copyQuotationApi/)
  assert.doesNotMatch(copyFlow, /refreshQuotations/)
})

test('copied quotation data is treated as create-form prefill', () => {
  assert.match(app, /:copy-quote="copySourceQuote"/)
  assert.match(create, /copyQuote\?: Quotation \| null/)
  assert.match(create, /function loadCopiedQuoteIntoForm\(/)
  assert.match(create, /quoteNoMode\.value = 'auto'/)
  assert.match(create, /quoteDate\.value = todayInput/)
  assert.match(create, /applyingCreateDraft\.value = false\n    if \(quoteNoMode\.value === 'auto'\) regenerateQuoteNo\(\)/)
  assert.match(create, /props\.editingQuote \|\| props\.copyQuote \|\| applyingCreateDraft\.value/)
})
