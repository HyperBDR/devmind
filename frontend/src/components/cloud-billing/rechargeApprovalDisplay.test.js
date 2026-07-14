import assert from 'node:assert/strict'
import test from 'node:test'

import { getRechargeApprovalSnapshot } from './rechargeApprovalDisplay.js'

test('formats balance alert snapshot with its currency', () => {
  const snapshot = getRechargeApprovalSnapshot({
    context_payload: {
      current_balance: '407.52',
      balance_threshold: '500.00'
    },
    request_payload: {
      amount: '358',
      currency: 'CNY'
    }
  })

  assert.deepEqual(snapshot, {
    submittedBalance: '407.52 CNY',
    threshold: '500.00 CNY',
    rechargeAmount: '358 CNY'
  })
})

test('formats days-remaining threshold and falls back to raw request data', () => {
  const snapshot = getRechargeApprovalSnapshot(
    {
      context_payload: {
        current_balance: '96.20',
        days_remaining_threshold: '7'
      },
      raw_recharge_info: JSON.stringify({
        amount: '200 USD',
        currency: 'USD'
      })
    },
    { daysUnit: '天' }
  )

  assert.deepEqual(snapshot, {
    submittedBalance: '96.20 USD',
    threshold: '7 天',
    rechargeAmount: '200 USD'
  })
})

test('uses a dash for unavailable approval snapshot values', () => {
  assert.deepEqual(getRechargeApprovalSnapshot({}), {
    submittedBalance: '-',
    threshold: '-',
    rechargeAmount: '-'
  })
})

test('parses supported key-value recharge text for failed records', () => {
  const snapshot = getRechargeApprovalSnapshot({
    raw_recharge_info: [
      '充值云账号：acct-188',
      '付款金额：200.00 CNY'
    ].join('\n')
  })

  assert.equal(snapshot.rechargeAmount, '200.00 CNY')
})
