import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildCloudBillingAccountSearchText,
  cloudBillingAccountMatchesQuery
} from '../src/utils/cloudBillingAccountSearch.js'

const account = {
  name: '阿里云',
  provider: '阿里云',
  provider_type: 'alibaba',
  account_id: '5776349018366354',
  notes: '[SaaS使用]账号ID: 5776349018366354',
  category: 'HyperBDR',
  type: 'prepaid',
  tags: ['[国际]HyperBDR', 'HyperBDR', '充值']
}

const context = {
  accountLabel: '阿里云',
  providerLabel: '阿里云',
  paymentTypeLabel: '预付费',
  providerAliases: ['alibaba', 'aliyun', '阿里云', 'alibaba cloud']
}

test('matches the localized account and platform label', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '阿里云', context),
    true
  )
})

test('matches cross-locale provider aliases', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, 'alibaba', context),
    true
  )
  assert.equal(
    cloudBillingAccountMatchesQuery(account, 'aliyun', context),
    true
  )
  assert.equal(
    cloudBillingAccountMatchesQuery(account, 'Alibaba Cloud', context),
    true
  )
})

test('matches the account id', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '5776349018366354', context),
    true
  )
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '5776', context),
    true
  )
})

test('matches provider notes', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, 'saas使用', context),
    true
  )
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '账号id', context),
    true
  )
})

test('matches provider tags and category', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, 'hyperbdr', context),
    true
  )
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '充值', context),
    true
  )
})

test('requires every token of a multi-keyword query', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '阿里云 hyperbdr', context),
    true
  )
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '阿里云 不存在的词', context),
    false
  )
})

test('treats an empty query as a match', () => {
  assert.equal(cloudBillingAccountMatchesQuery(account, '   ', context), true)
})

test('rejects unrelated queries', () => {
  assert.equal(
    cloudBillingAccountMatchesQuery(account, '华为云', context),
    false
  )
})

test('exposes a combined searchable text blob', () => {
  const text = buildCloudBillingAccountSearchText(account, context)
  assert.ok(text.includes('alibaba'))
  assert.ok(text.includes('5776349018366354'))
  assert.ok(text.includes('hyperbdr'))
})
