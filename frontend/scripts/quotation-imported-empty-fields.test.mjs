import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const previewModel = await readFile(
  new URL('../src/modules/quotation/utils/quotationPreviewModel.ts', import.meta.url),
  'utf8',
)
const app = await readFile(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)

test('imported quotations do not fall back to the logged-in issuer', () => {
  assert.match(previewModel, /sourceType === 'document_import'/)
  assert.match(previewModel, /fallbackUser = isImportedQuotation \? undefined/)
  assert.match(previewModel, /fallbackSalesperson = isImportedQuotation \? ''/)
  assert.match(previewModel, /fallbackName = isImportedQuotation/)
  assert.match(previewModel, /fallbackEmail = isImportedQuotation/)
  assert.match(previewModel, /name: quote\.issuerContactName\?\.trim\(\) \|\| fallbackName/)
  assert.match(previewModel, /email: quote\.issuerContactEmail\?\.trim\(\) \|\| fallbackEmail/)
})

test('quotation details switch immediately while the full quote loads', () => {
  assert.match(app, /currentTab\.value = 'details'[\s\S]{0,160}loadActiveQuote/)
  assert.match(app, /currentTab === 'details' && activeQuoteLoading/)
})
