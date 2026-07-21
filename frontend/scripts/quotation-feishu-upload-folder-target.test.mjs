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

test('Feishu upload asks for a configured archive subfolder first', () => {
  assert.match(source, /FeishuFolderPickerModal/)
  assert.match(source, /uploadFolderPicker\.value = \{ quote, format \}/)
  assert.match(source, /handleUploadFolderSelected/)
  assert.match(source, /folderToken/)
  assert.doesNotMatch(source, /FeishuDriveModal/)
  assert.match(enLocale, /"toastUploadFailed": "Upload to Feishu failed\. Check the archive folder configuration"/)
})
