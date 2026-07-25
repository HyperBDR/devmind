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

test('Feishu upload uses the backend configured archive mount', () => {
  assert.match(source, /archiveQuotationFile\(quote\.id, exportFormat/)
  assert.doesNotMatch(source, /FeishuFolderPickerModal/)
  assert.doesNotMatch(source, /uploadFolderPicker/)
  assert.doesNotMatch(source, /handleUploadFolderSelected/)
  assert.doesNotMatch(source, /folderToken/)
  assert.match(enLocale, /"toastUploadFailed": "Upload to Feishu failed\. Check the archive folder configuration"/)
})
