import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const feishuApi = await readFile(
  new URL('../src/modules/quotation/api/feishu.ts', import.meta.url),
  'utf8'
)
const authStore = await readFile(
  new URL('../src/modules/quotation/stores/auth.ts', import.meta.url),
  'utf8'
)
const importsPage = await readFile(
  new URL(
    '../src/modules/quotation/components/ImportedDocumentsPage.vue',
    import.meta.url
  ),
  'utf8'
)
const zhCn = await readFile(
  new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
  'utf8'
)
const en = await readFile(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8'
)

test('authentication bootstrap starts one scoped Feishu synchronization', () => {
  assert.match(feishuApi, /triggerFeishuLoginSync/)
  assert.match(feishuApi, /feishu\/sync-on-login/)
  assert.match(authStore, /triggerFeishuLoginSync/)
  assert.match(authStore, /quotation-feishu-login-sync:/)
})

test('quotation UI renders synchronization state and safe differences', () => {
  assert.match(feishuApi, /getFeishuSyncStatus/)
  assert.match(feishuApi, /feishu\/sync-status/)
  assert.match(importsPage, /syncOverview/)
  assert.match(importsPage, /syncDifferenceLabel/)
  assert.match(importsPage, /syncStateLabel/)
  assert.match(importsPage, /difference\.file_name/)
  assert.doesNotMatch(importsPage, /difference\.file_token/)
})

test('manual synchronization and retry use the same durable endpoint', () => {
  assert.match(importsPage, /handleSyncNow/)
  assert.match(importsPage, /syncFeishuArchiveFolder/)
  assert.match(importsPage, /syncRetry/)
})

test('administrators can resolve Feishu deletion differences', () => {
  assert.match(feishuApi, /resolveFeishuSyncDifference/)
  assert.match(importsPage, /handleResolveDifference/)
  assert.match(importsPage, /syncArchiveDifference/)
  assert.match(importsPage, /syncDeleteDifference/)
})

test('sync status copy is bilingual', () => {
  for (const source of [zhCn, en]) {
    assert.match(source, /"syncStatus"/)
    assert.match(source, /"syncHasDiff"/)
    assert.match(source, /"syncPermission"/)
    assert.match(source, /"syncMissing"/)
    assert.match(source, /"syncRetry"/)
  }
})
