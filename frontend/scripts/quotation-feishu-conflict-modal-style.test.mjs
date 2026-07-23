import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(
  new URL('../src/modules/quotation/components/QuotationList.vue', import.meta.url),
  'utf8',
)
const enLocale = readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
)

test('duplicate upload dialog follows the Feishu modal visual language', () => {
  assert.match(source, /v-if="uploadConflict"[\s\S]*max-w-md[\s\S]*rounded-xl border border-slate-200/)
  assert.match(source, /border-b border-slate-100 px-5 py-4/)
  assert.match(source, /bg-blue-50 text-blue-600/)
  assert.match(source, /<X class="h-4 w-4"/)
  assert.match(source, /bg-slate-50\/40 px-5 py-4/)
  assert.match(source, /class="dm-btn-primary h-9 whitespace-nowrap px-3\.5 text-sm font-semibold"[\s\S]*resolveUploadConflict\('rename'\)/)
  assert.match(source, /whitespace-nowrap/)
  assert.match(enLocale, /"conflictTitle": "File already exists"/)
  assert.match(enLocale, /"conflictDesc": "\{fileName\} is already in this folder\."/)
  assert.match(enLocale, /"reuseExistingFile": "Use existing"/)
  assert.match(enLocale, /"renameAndUpload": "Upload a copy"/)
  assert.match(enLocale, /"cancelUpload": "Cancel"/)
  assert.doesNotMatch(source, /max-w-lg rounded-2xl border border-amber-200/)
  assert.doesNotMatch(source, /bg-blue-600[\s\S]*hover:bg-blue-700/)
  assert.doesNotMatch(source, /bg-emerald-600 px-4 py-3/)
})
