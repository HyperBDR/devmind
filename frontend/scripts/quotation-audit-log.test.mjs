import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const auditPage = readFileSync(
  new URL(
    '../src/modules/quotation/components/AuditLogPage.vue',
    import.meta.url,
  ),
  'utf8',
)
const auditApi = readFileSync(
  new URL('../src/modules/quotation/api/audit.ts', import.meta.url),
  'utf8',
)
const feishuApi = readFileSync(
  new URL('../src/modules/quotation/api/feishu.ts', import.meta.url),
  'utf8',
)
const quotationList = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationList.vue',
    import.meta.url,
  ),
  'utf8',
)
const exportsApi = readFileSync(
  new URL('../src/modules/quotation/api/exports.ts', import.meta.url),
  'utf8',
)
const sidebar = readFileSync(
  new URL('../src/components/layout/AppSidebar.vue', import.meta.url),
  'utf8',
)
const english = JSON.parse(
  readFileSync(
    new URL('../src/modules/quotation/locales/en.json', import.meta.url),
    'utf8',
  ),
)

test('Audit Log is visible to Quote Desk users and remains read-only', () => {
  assert.match(sidebar, /to="\/quotation\/audit"/)
  assert.match(auditApi, /apiRequest<AuditEventPage>/)
  assert.match(auditApi, /`\/audit-events\?\$\{params\.toString\(\)\}`/)
  assert.match(auditPage, /quotation\.pages\.audit\.viewDetails/)
  assert.match(auditPage, /<FormSelect/)
  assert.match(auditPage, /<BaseDatePicker/)
  assert.match(auditPage, /downloadAuditExport/)
  assert.doesNotMatch(auditPage, /riskFilter/)
  assert.doesNotMatch(auditPage, /selected\.risk_level/)
  assert.doesNotMatch(auditPage, /syncFolderNames|hasSyncMetrics/)
  assert.match(auditPage, /buildAuditChangeLines/)
  assert.match(auditPage, /selected\.changes\.fields\.map\(fieldLabel\)/)
  assert.match(auditPage, /selected\.trace_id/)
  assert.doesNotMatch(auditPage, /<select/)
})

test('Audit Log renders JSON additions and removals with semantic colors', () => {
  assert.match(auditPage, /buildAuditChangeLines/)
  assert.match(auditPage, /data-change-line-removed/)
  assert.match(auditPage, /data-change-line-added/)
  assert.match(auditPage, /bg-red-50/)
  assert.match(auditPage, /bg-emerald-50/)
  assert.match(auditPage, /linePrefix\(line\.kind\)/)
})

test('background Feishu return checks do not duplicate open audits', () => {
  assert.match(feishuApi, /auditSource\?: 'automatic' \| 'user'/)
  assert.match(feishuApi, /X-Quotation-Audit-Source/)
  assert.match(
    quotationList,
    /checkFeishuFileAccess\(pending\.documentId, \{[\s\S]*auditSource: 'automatic'/,
  )
  const consumePending = quotationList.indexOf(
    'pendingFeishuOpen.value = null',
  )
  const backgroundCheck = quotationList.indexOf(
    'checkFeishuFileAccess(pending.documentId',
  )
  assert.ok(consumePending >= 0)
  assert.ok(backgroundCheck > consumePending)
})

test('server-generated quotation assets use the audited download API', () => {
  assert.match(exportsApi, /\/documents\/\$\{encodeURIComponent\(asset\.id\)\}\/download/)
  assert.match(
    quotationList,
    /exportQuotationFile\(quote\.id, exportFormat, \{[\s\S]*onProgress/,
  )
})

test('Audit Log has no security-alert workflow or API dependency', () => {
  assert.doesNotMatch(auditPage, /SecurityAlertsPanel|securityAlerts/)
  assert.doesNotMatch(auditApi, /SecurityAlert|security-alerts/)
})

test('Audit Log normalizes legacy module keys before display', () => {
  assert.match(auditPage, /moduleAliases/)
  assert.match(auditPage, /quote:\s*'quotation'/)
  assert.match(auditPage, /normalizedModule/)
  assert.match(auditPage, /fallbackLabel/)
  assert.match(auditPage, /inline-flex max-w-full truncate/)
})

test('Audit Log gives missing business targets a useful label', () => {
  assert.doesNotMatch(auditPage, /targetFallbackByOperation/)
  assert.match(auditPage, /targetFallbackByType/)
  assert.match(auditPage, /quotation\.pages\.audit\.targets/)
  assert.equal(english.quotation.pages.audit.targets.document, 'File')
  assert.equal(english.quotation.pages.audit.targets.quotation, 'Quotation')
})

test('Audit Log uses concise, native English product copy', () => {
  const copy = english.quotation.pages.audit
  assert.equal(copy.title, 'Audit Log')
  assert.equal(copy.performedBy, 'Performed by')
  assert.equal(copy.readOnly, 'Read-only activity records')
  assert.equal(copy.actions.generate, 'Generated quote')
  assert.equal(copy.actions.updatedQuote, 'Updated quote')
  assert.equal(copy.actions.deletedQuote, 'Deleted quote')
  assert.equal(copy.actions.deletedCatalogItem, 'Deleted catalog item')
  assert.equal(copy.actions.archive, 'Archived file')
  assert.equal(copy.actions.restore, 'Restored file')
  assert.equal(copy.catalogItemTypes.software_product, 'Software product')
  assert.equal(copy.viewVersionHistory, 'View quote history')
  assert.equal(copy.succeeded, 'Succeeded')
  assert.equal(copy.denied, 'Denied')
  assert.equal(copy.exportCsv, 'Export CSV')
  assert.equal(copy.failed, 'Failed')
})

test('Audit Log only offers approved business action filters', () => {
  for (const action of [
    'create',
    'update',
    'delete',
    'generate',
    'upload',
    'download',
    'import',
    'archive',
    'restore',
  ]) {
    assert.match(auditPage, new RegExp(`'${action}'`))
  }
  assert.doesNotMatch(auditPage, /'view'|'sync'|'open'|'connect'/)
  assert.doesNotMatch(
    auditPage,
    /storage\.archive_sync_|viewedAuditLog|syncSuccessCount/,
  )
})
