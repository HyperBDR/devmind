import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const feishuApi = readFileSync(
  new URL('../src/modules/quotation/api/feishu.ts', import.meta.url),
  'utf8'
)

const importsPage = readFileSync(
  new URL('../src/modules/quotation/components/ImportedDocumentsPage.vue', import.meta.url),
  'utf8'
)
const folderPicker = readFileSync(
  new URL('../src/modules/quotation/components/FeishuFolderPickerModal.vue', import.meta.url),
  'utf8'
)
const quotationApp = readFileSync(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8'
)
const appSidebar = readFileSync(
  new URL('../src/components/layout/AppSidebar.vue', import.meta.url),
  'utf8'
)
const router = readFileSync(
  new URL('../src/router/index.js', import.meta.url),
  'utf8'
)

test('Feishu archive refresh keeps original access and uses document IDs', () => {
  assert.match(feishuApi, /syncFeishuArchiveFolder/)
  assert.match(feishuApi, /\/feishu\/sync-folder/)
  assert.match(importsPage, /syncFeishuArchiveFolder/)
  assert.match(importsPage, /syncSource: 'automatic'/)
  assert.match(importsPage, /syncSource: 'user'/)
  assert.match(importsPage, /options\.syncSource !== 'automatic'/)
  assert.match(feishuApi, /X-Quotation-Audit-Source/)
  assert.doesNotMatch(importsPage, /canSyncArchive/)
  assert.match(importsPage, /checkFeishuFileAccess\(doc\.id\)/)
  assert.match(importsPage, /doc\.feishu_folder_path/)
  assert.match(importsPage, /rebuildArchiveTree\(items\)/)
  assert.doesNotMatch(importsPage, /__ungrouped__/)
  assert.doesNotMatch(importsPage, /ungroupedDocs/)
  assert.doesNotMatch(importsPage, /window\.open\(result\.url/)
  assert.match(importsPage, /window\.open\(directUrl, '_blank', 'noopener,noreferrer'\)/)
  assert.doesNotMatch(importsPage, /downloadRemoteDocument/)
  assert.doesNotMatch(importsPage, /batchCheckFeishuFileAccess/)
  assert.doesNotMatch(importsPage, /getFeishuStatus/)
  assert.match(feishuApi, /feishu\/documents\/.*\/access/)
  assert.doesNotMatch(feishuApi, /feishu\/files\/.*\/access/)
  assert.doesNotMatch(importsPage, /FeishuFolderPickerModal/)
  assert.doesNotMatch(importsPage, /folderToken:\s*folder\.token/)
  assert.match(folderPicker, /listFeishuFolder/)
})

test('Imported files panel no longer opens a personal Feishu drive picker', () => {
  assert.doesNotMatch(importsPage, /FeishuDriveModal/)
  assert.doesNotMatch(importsPage, /startFeishuOAuth/)
  assert.match(importsPage, /syncButton/)
})

test('Imported files browser stays mounted while its visible panels are hidden', () => {
  assert.match(importsPage, /id="import-filter-panel"\s+v-show="false"/)
  assert.match(importsPage, /id="import-table-panel"\s+v-show="false"/)
  assert.match(importsPage, /void refresh\(\{ syncRemote: true, syncSource: 'automatic' \}\)/)
  assert.match(importsPage, /listImportedFeishuDocuments\(\)/)
  assert.match(importsPage, /syncFeishuArchiveFolder\(/)
  assert.match(importsPage, /downloadImportedDocument\(doc\.id, doc\.file_name\)/)
  assert.match(importsPage, /deleteImportedDocuments\(ids\)/)
})

test('imported Feishu files live under the Quotes page', () => {
  assert.match(quotationApp, /QuotationList/)
  assert.match(quotationApp, /ImportedDocumentsPage/)
  assert.match(quotationApp, /embedded/)
  assert.doesNotMatch(quotationApp, /quoteListPanel/)
  assert.doesNotMatch(quotationApp, /tabImports/)
  assert.doesNotMatch(quotationApp, /setQuoteListPanel/)
  assert.doesNotMatch(quotationApp, /id="nav-tab-imports"/)
  assert.doesNotMatch(appSidebar, /to="\/quotation\/imports"/)
  assert.match(router, /path:\s*'\/quotation\/imports'[\s\S]*redirect:\s*\{[\s\S]*path:\s*'\/quotation\/list'[\s\S]*\}/)
  assert.doesNotMatch(router, /tab:\s*'imports'/)
})
