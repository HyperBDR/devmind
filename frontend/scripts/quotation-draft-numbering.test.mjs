import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const api = await readFile(
  new URL('../src/modules/quotation/api/quotations.ts', import.meta.url),
  'utf8',
)
const create = await readFile(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const app = await readFile(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)
const english = JSON.parse(
  await readFile(
    new URL('../src/modules/quotation/locales/en.json', import.meta.url),
    'utf8',
  ),
)
const chinese = JSON.parse(
  await readFile(
    new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
    'utf8',
  ),
)
const normalizedApi = api.replace(/\s+/g, ' ')
const normalizedCreate = create.replace(/\s+/g, ' ')

test('draft payloads keep predicted numbers outside formal quote_no', () => {
  assert.match(normalizedApi, /quote\.status === 'Draft' \? undefined : quote\.quoteNo/)
  assert.match(normalizedApi, /quote\.status === 'Draft' \? quote\.quoteNo \|\| '' : undefined/)
  assert.match(normalizedApi, /draft_quote_no: options\?\.draftQuoteNo/)
  assert.match(normalizedApi, /numbering_mode: options\?\.quoteNoMode/)
  assert.match(app, /quoteNoMode: ownedQuote\.quoteNoMode/)
  assert.match(app, /draftQuoteNo: ownedQuote\.quoteNo/)
})

test('draft previews do not participate in frontend formal-number checks', () => {
  assert.match(
    normalizedCreate,
    /filter\(\(quote\) => quote\.status !== 'Draft'\)/,
  )
  assert.match(normalizedCreate, /draftLifecycleForm\.value \|\| quoteNoMode\.value === 'auto'/)
  assert.match(create, /quoteNumberHintDraft/)
})

test('draft-numbering copy explains preview-only behavior in both locales', () => {
  assert.match(
    english.quotation.pages.create.quoteNumberHintDraft,
    /Preview only while drafting/,
  )
  assert.match(
    chinese.quotation.pages.create.quoteNumberHintDraft,
    /预测展示/,
  )
})
