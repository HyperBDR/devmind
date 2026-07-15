import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { syncJobError, syncJobFailureDetails } from '../src/utils/sync.js'

const dataOpsApi = readFileSync(
  new URL('../src/api/dataOps.js', import.meta.url),
  'utf8'
)
const dataOpsConsole = readFileSync(
  new URL('../src/composables/useDataOpsConsole.js', import.meta.url),
  'utf8'
)
const dataOpsHeader = readFileSync(
  new URL('../src/components/data-ops/DataOpsHeader.vue', import.meta.url),
  'utf8'
)
const dataOpsPage = readFileSync(
  new URL('../src/pages/DataOps.vue', import.meta.url),
  'utf8'
)
const executiveSection = readFileSync(
  new URL('../src/components/data-ops/ExecutiveSection.vue', import.meta.url),
  'utf8'
)
const syncSection = readFileSync(
  new URL('../src/components/data-ops/SyncSection.vue', import.meta.url),
  'utf8'
)
const syncFailureDetails = readFileSync(
  new URL('../src/components/data-ops/SyncFailureDetails.vue', import.meta.url),
  'utf8'
)
const collectionConfigSection = readFileSync(
  new URL(
    '../src/components/data-ops/CollectionConfigSection.vue',
    import.meta.url
  ),
  'utf8'
)

test('refresh requests a conditional Feishu sync and reports progress', () => {
  assert.match(dataOpsApi, /triggerRefreshSync[\s\S]*force:\s*false/)
  assert.match(dataOpsConsole, /refreshFromFeishu[\s\S]*waitForSyncJob/)
  assert.match(dataOpsHeader, /dataOps\.header\.refreshing/)
})

test('keeps full sync busy until its job reaches a terminal status', () => {
  assert.match(
    dataOpsConsole,
    /triggerFullSync[\s\S]*triggerSync\(\)[\s\S]*waitForSyncJob/
  )
  assert.match(dataOpsConsole, /if \(syncLoading\.value\) return false/)
  assert.match(dataOpsHeader, /dataOps\.header\.syncing/)
  assert.match(dataOpsHeader, /:aria-busy="syncLoading"/)
})

test('only exposes incremental sync actions for active data sources', () => {
  const syncBanner = readFileSync(
    new URL(
      '../src/components/data-ops/DataOpsSyncBanner.vue',
      import.meta.url
    ),
    'utf8'
  )

  assert.match(syncBanner, /key:\s*'domestic'/)
  assert.doesNotMatch(syncBanner, /key:\s*'oversea'/)
  assert.doesNotMatch(syncBanner, /key:\s*'oversea_stats'/)
})

test('shows stable loading styles for refresh and full sync actions', () => {
  assert.match(dataOpsHeader, /'animate-spin': loading/)
  assert.match(dataOpsHeader, /'animate-spin': syncLoading/)
  assert.match(dataOpsHeader, /disabled:cursor-wait/)
})

test('summarizes failed Feishu tables with the first actionable error', () => {
  const message = syncJobError({
    results: {
      contracts: { status: 'failed', message: '合同表记录读取权限不足。' },
      projects: { status: 'failed', message: '项目表记录读取权限不足。' }
    }
  })

  assert.equal(message, '2 张飞书表同步失败：合同表记录读取权限不足。')
})

test('builds actionable and sanitized Feishu failure details', () => {
  const failure = syncJobFailureDetails({
    results: {
      'domestic.contracts': {
        status: 'failed',
        issue_code: 'table_access_denied',
        message: '合同表记录读取权限不足。',
        resolution_hint: '请确认飞书应用已添加到该多维表格。',
        feishu_detail: {
          stage: '记录读取',
          http_status: 403,
          feishu_code: 91403,
          feishu_msg: 'Forbidden',
          api_url: 'https://open.feishu.cn/open-apis/private-path',
          table_url: 'https://www.feishu.cn/base/base-id?table=table-id',
          request_headers: {
            Authorization: 'Bearer secret',
            'x-request-id': 'request-123',
            'x-tt-logid': 'log-456'
          }
        }
      }
    }
  })

  assert.equal(failure.summary, '合同表记录读取权限不足。')
  assert.equal(failure.items[0].stage, '记录读取')
  assert.equal(failure.items[0].httpStatus, 403)
  assert.equal(failure.items[0].feishuCode, 91403)
  assert.equal(failure.items[0].requestId, 'request-123')
  assert.equal(failure.items[0].logId, 'log-456')
  assert.match(failure.items[0].suggestions.join(''), /同一个多维表格/)
  assert.equal(
    failure.items[0].tableUrl,
    'https://www.feishu.cn/base/base-id?table=table-id'
  )
  assert.doesNotMatch(JSON.stringify(failure), /Bearer secret|private-path/)
})

test('rejects non-Feishu links from sync failure details', () => {
  const failure = syncJobFailureDetails({
    results: {
      contracts: {
        status: 'failed',
        message: '读取失败。',
        feishu_detail: {
          table_url: 'https://example.com/unsafe'
        }
      }
    }
  })

  assert.equal(failure.items[0].tableUrl, '')
})

test('renders structured sync failures with trace IDs and suggestions', () => {
  assert.match(dataOpsConsole, /syncJobFailureDetails\(job\)/)
  assert.match(dataOpsPage, /<SyncFailureDetails/)
  assert.match(syncFailureDetails, /item\.requestId/)
  assert.match(syncFailureDetails, /item\.suggestions/)
  assert.match(syncFailureDetails, /rel="noopener noreferrer"/)
})

test('renders Feishu collection configs as a read-only directory', () => {
  assert.doesNotMatch(collectionConfigSection, /<input|<textarea|<select/)
  assert.doesNotMatch(collectionConfigSection, /最低记录|>权限</)
  assert.doesNotMatch(collectionConfigSection, />\s*保存\s*</)
  assert.match(collectionConfigSection, /config\.table_url/)
  assert.match(collectionConfigSection, /dataOps\.config\.openTable/)
  assert.match(collectionConfigSection, /rel="noopener noreferrer"/)
})

test('removes the manual owner assignment feature', () => {
  assert.doesNotMatch(dataOpsPage, /OwnerAliasManager|负责人归属/)
  assert.doesNotMatch(dataOpsApi, /ownerAliases|owner-aliases/)
})

test('opens an accessible detail dialog from an action item', () => {
  assert.match(executiveSection, /v-for="item in actionItems"/)
  assert.match(executiveSection, /@click="openAction\(item, \$event\)"/)
  assert.match(executiveSection, /role="dialog"/)
  assert.match(executiveSection, /aria-modal="true"/)
  assert.match(executiveSection, /selectedAction/)
  assert.match(executiveSection, /@click\.self="closeActionDetail"/)
})

test('shows data quality under sync status instead of business tabs', () => {
  assert.doesNotMatch(executiveSection, /label:\s*'数据质量'/)
  assert.doesNotMatch(executiveSection, /activeTab === 'quality'/)
  assert.match(dataOpsPage, /<SyncSection[\s\S]*:data-quality="dataQuality"/)
  assert.match(syncSection, /<DataQualityPanel/)
  assert.match(syncSection, /:data-quality="dataQuality"/)
})
