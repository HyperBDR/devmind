import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(
  new URL('../src/modules/quotation/components/FeishuDriveModal.vue', import.meta.url),
  'utf8',
)
const enLocale = readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
)

test('Feishu upload picker requires an explicit non-root folder target', () => {
  assert.match(source, /const isRootUploadTarget = computed/)
  assert.match(source, /props\.pickIntent === 'upload'/)
  assert.match(source, /driveTree\.value\?\.my_root\?\.token/)
  assert.match(source, /toastSelectUploadFolder/)
  assert.match(source, /isRootUploadTarget/)
  assert.match(source, /:disabled="!connected \|\| !currentToken \|\| isRootUploadTarget \|\| loading"/)
  assert.match(enLocale, /"uploadRootDisabledHint": "Open a folder before uploading; files are not uploaded to My Space root\."/)
})
