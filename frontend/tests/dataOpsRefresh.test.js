import assert from 'node:assert/strict'
import test from 'node:test'

import { syncJobError, syncJobFailureDetails } from '../src/utils/sync.js'

test('summarizes failed Feishu tables with the first actionable error', () => {
  const message = syncJobError({
    results: {
      contracts: { status: 'failed', message: '合同表记录读取权限不足。' },
      projects: { status: 'failed', message: '项目表记录读取权限不足。' }
    }
  })

  assert.equal(message, '2 张飞书表同步失败：合同表记录读取权限不足。')
})

test('builds sanitized Feishu failure details', () => {
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
          table_url: 'https://www.feishu.cn/base/test-base?table=test-table',
          request_headers: {
            Authorization: 'Bearer test-token',
            'x-request-id': 'test-request-id',
            'x-tt-logid': 'test-log-id'
          }
        }
      }
    }
  })

  assert.equal(failure.summary, '合同表记录读取权限不足。')
  assert.equal(failure.items[0].stage, '记录读取')
  assert.equal(failure.items[0].httpStatus, 403)
  assert.equal(failure.items[0].feishuCode, 91403)
  assert.equal(failure.items[0].requestId, 'test-request-id')
  assert.equal(failure.items[0].logId, 'test-log-id')
  assert.match(failure.items[0].suggestions.join(''), /同一个多维表格/)
  assert.equal(
    failure.items[0].tableUrl,
    'https://www.feishu.cn/base/test-base?table=test-table'
  )
  assert.doesNotMatch(JSON.stringify(failure), /Bearer test-token|private-path/)
})

test('rejects non-Feishu links from sync failure details', () => {
  const failure = syncJobFailureDetails({
    results: {
      contracts: {
        status: 'failed',
        message: '读取失败。',
        feishu_detail: {
          table_url: 'https://example.test/unsafe'
        }
      }
    }
  })

  assert.equal(failure.items[0].tableUrl, '')
})
