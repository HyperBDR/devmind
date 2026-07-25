import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(
  new URL('../src/modules/quotation/components/QuotationList.vue', import.meta.url),
  'utf8',
)
const archiveApi = readFileSync(
  new URL('../src/modules/quotation/api/exports.ts', import.meta.url),
  'utf8',
)

test('Feishu file conflicts are resolved by the backend mount policy', () => {
  assert.match(source, /archiveQuotationFile\(quote\.id, exportFormat/)
  assert.match(archiveApi, /archive_to_feishu: options\.archiveToFeishu \?\? false/)
  assert.doesNotMatch(source, /uploadConflict/)
  assert.doesNotMatch(source, /resolveUploadConflict/)
  assert.doesNotMatch(source, /conflict_policy/)
})
