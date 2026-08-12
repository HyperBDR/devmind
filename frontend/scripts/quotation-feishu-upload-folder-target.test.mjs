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
const archiveApi = readFileSync(
  new URL('../src/modules/quotation/api/exports.ts', import.meta.url),
  'utf8',
)

test('Feishu upload lets the user choose a managed archive folder', () => {
  assert.match(source, /archiveQuotationFile\(quote\.id, exportFormat/)
  assert.match(source, /FeishuFolderPickerModal/)
  assert.match(source, /folderPickerOpen/)
  assert.match(source, /handleFeishuFolderSelected/)
  assert.match(source, /archiveFolderToken/)
  assert.match(archiveApi, /archive_folder_token: options\.archiveFolderToken/)
  assert.match(enLocale, /"toastUploadFailed": "Upload to Feishu failed\. Check the archive folder configuration"/)
})
