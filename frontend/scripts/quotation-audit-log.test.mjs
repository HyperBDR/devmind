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
const securityPanel = readFileSync(
  new URL(
    '../src/modules/quotation/components/SecurityAlertsPanel.vue',
    import.meta.url,
  ),
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
  assert.match(auditPage, /riskFilter/)
  assert.match(auditPage, /selected\.trace_id/)
  assert.doesNotMatch(auditPage, /<select/)
})

test('Security Alerts follows the reviewed three-step workflow', () => {
  assert.match(auditPage, /SecurityAlertsPanel/)
  assert.match(securityPanel, /listSecurityAlerts/)
  assert.match(securityPanel, /getSecurityAlert/)
  assert.match(securityPanel, /updateSecurityAlert/)
  assert.match(securityPanel, /action:\s*'acknowledge'/)
  assert.match(securityPanel, /action:\s*'resolve'/)
  assert.match(securityPanel, /v-if="canManage/)
  assert.match(securityPanel, /object_id_enumeration/)
  assert.match(securityPanel, /selected\.runbook/)
  assert.match(securityPanel, /fixed inset-x-0 bottom-0 top-12/)
  assert.match(securityPanel, /<FormSelect/)
  assert.doesNotMatch(securityPanel, /<select/)
})

test('Security Alerts KPI icons stay compact and low contrast', () => {
  assert.match(securityPanel, /metricIconClass/)
  assert.match(securityPanel, /h-9 w-9[^"]*rounded-lg[^"]*border/)
  assert.match(securityPanel, /class="h-4 w-4/)
  assert.doesNotMatch(
    securityPanel,
    /rounded-xl bg-(red|orange|blue)-50 p-3/,
  )
})

test('Audit Log normalizes legacy module keys before display', () => {
  assert.match(auditPage, /moduleAliases/)
  assert.match(auditPage, /quote:\s*'quotation'/)
  assert.match(auditPage, /normalizedModule/)
  assert.match(auditPage, /fallbackLabel/)
  assert.match(auditPage, /inline-flex max-w-full truncate/)
})

test('Audit Log gives missing historical targets a useful label', () => {
  assert.match(auditPage, /targetFallbackByOperation/)
  assert.match(auditPage, /targetFallbackByType/)
  assert.match(auditPage, /'audit\.view': 'auditLog'/)
  assert.match(auditPage, /'feishu\.sync': 'archiveFolder'/)
  assert.match(auditPage, /quotation\.pages\.audit\.targets/)
  assert.equal(
    english.quotation.pages.audit.targets.auditLog,
    'Audit log',
  )
  assert.equal(
    english.quotation.pages.audit.targets.archiveFolder,
    'Feishu archive folder',
  )
  assert.match(auditPage, /moduleKey === 'audit'/)
  assert.equal(
    english.quotation.pages.audit.actions.viewedAuditLog,
    'Viewed audit log',
  )
})

test('Audit Log uses concise, native English product copy', () => {
  const copy = english.quotation.pages.audit
  assert.equal(copy.title, 'Audit Log')
  assert.equal(copy.performedBy, 'Performed by')
  assert.equal(copy.readOnly, 'Read-only activity records')
  assert.equal(copy.actions.view, 'Viewed quote')
  assert.equal(copy.actions.updatedQuote, 'Updated quote')
  assert.equal(copy.actions.deletedQuote, 'Deleted quote')
  assert.equal(copy.actions.deletedFile, 'Deleted file')
  assert.equal(copy.actions.deletedCatalogItem, 'Deleted catalog item')
  assert.equal(copy.catalogItemTypes.software_product, 'Software product')
  assert.equal(copy.actions.download, 'Downloaded file')
  assert.equal(copy.viewVersionHistory, 'View quote history')
  assert.equal(copy.succeeded, 'Succeeded')
  assert.equal(copy.denied, 'Denied')
  assert.equal(copy.exportCsv, 'Export CSV')
  assert.equal(copy.failed, 'Failed')
  assert.equal(copy.activityLog, 'Activity Log')
  assert.equal(copy.securityAlerts, 'Security Alerts')
  assert.equal(copy.security.resolveAlert, 'Resolve alert')
  assert.equal(
    copy.security.resolutions.authorized_activity,
    'Authorized business activity',
  )
})
