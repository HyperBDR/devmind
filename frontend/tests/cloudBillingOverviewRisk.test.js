import assert from 'node:assert/strict'
import test from 'node:test'

import {
  cloudBillingAccountAttentionReasons,
  compareCloudBillingAccounts,
  hasCloudBillingBalance,
  isCloudBillingAccountCritical,
  selectCloudBillingTrendAccounts
} from '../src/utils/cloudBillingOverviewRisk.js'

const byValue = (account) => Number(account?.balance || 0)
const byCost = (account) => Number(account?.cost || 0)

test('collection failure remains visible beside debt and availability', () => {
  const reasons = cloudBillingAccountAttentionReasons({
    type: 'prepaid',
    balance: -12.34,
    is_available: false,
    is_data_stale: true,
    stale_reason: 'collection_failed',
    risk: 'high'
  })

  assert.deepEqual(reasons, [
    'collection_failed',
    'account_unavailable',
    'account_overdrawn'
  ])
})

test('prepaid debt remains visible in account details and exports', () => {
  assert.equal(
    hasCloudBillingBalance({ type: 'prepaid', balance: -12.34 }),
    true
  )
  assert.equal(
    hasCloudBillingBalance({ type: 'prepaid', balance: 0 }),
    true
  )
  assert.equal(
    hasCloudBillingBalance({ type: 'postpaid', balance: 0 }),
    false
  )
  assert.equal(
    hasCloudBillingBalance({ type: 'prepaid', balance: null }),
    false
  )
})

test('known debt is critical without days remaining reference', () => {
  const account = {
    type: 'prepaid',
    balance: -12.34,
    is_available: false,
    has_days_remaining_reference: false,
    risk: 'high'
  }

  assert.equal(isCloudBillingAccountCritical(account), true)
})

test('trend selection includes debt before referenced healthy accounts', () => {
  const healthy = Array.from({ length: 6 }, (_, index) => ({
    id: `healthy-${index}`,
    type: 'prepaid',
    balance: 100 + index,
    cost: 10,
    days_remaining: 20 + index,
    has_days_remaining_reference: true,
    risk: 'medium'
  }))
  const deepseek = {
    id: 'deepseek',
    type: 'prepaid',
    balance: -12.34,
    cost: 0,
    is_available: false,
    days_remaining: null,
    has_days_remaining_reference: false,
    risk: 'high'
  }

  const selected = selectCloudBillingTrendAccounts(
    [...healthy, deepseek],
    5,
    byValue,
    byCost
  )

  assert.equal(selected.length, 5)
  assert.equal(selected[0].id, 'deepseek')
  assert.equal(
    selected.some((account) => account.id === 'deepseek'),
    true
  )
})

test('trend selection keeps every critical account beyond the soft limit', () => {
  const critical = Array.from({ length: 6 }, (_, index) => ({
    id: `critical-${index}`,
    type: 'prepaid',
    balance: index === 0 ? -1 : 10 + index,
    cost: 0,
    is_data_stale: index > 0,
    risk: 'high',
    has_days_remaining_reference: false
  }))

  const selected = selectCloudBillingTrendAccounts(critical, 5, byValue, byCost)

  assert.equal(selected.length, 6)
})

test('stale account sorts before a healthy referenced account', () => {
  const stale = {
    id: 'stale',
    type: 'prepaid',
    balance: 20,
    cost: 0,
    is_data_stale: true,
    risk: 'high',
    has_days_remaining_reference: false
  }
  const healthy = {
    id: 'healthy',
    type: 'prepaid',
    balance: 100,
    cost: 10,
    days_remaining: 5,
    risk: 'high',
    has_days_remaining_reference: true
  }

  assert.ok(compareCloudBillingAccounts(stale, healthy, byValue, byCost) < 0)
})
