import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getRechargeDateBounds,
  isValidRechargeExpectedDate
} from '../src/utils/rechargeExpectedDate.js'

test('recharge dates use Beijing today at the UTC day boundary', () => {
  const now = new Date('2026-10-11T16:30:00Z')
  assert.deepEqual(getRechargeDateBounds(now), {
    today: '2026-10-12',
    minDate: '2026-10-13',
    defaultDate: '2026-10-15'
  })
  assert.equal(isValidRechargeExpectedDate('2026-10-11', now), false)
  assert.equal(isValidRechargeExpectedDate('2026-10-12', now), false)
  assert.equal(isValidRechargeExpectedDate('2026-10-13', now), true)
  assert.equal(isValidRechargeExpectedDate('2026-10-15', now), true)
})

test('date bounds handle year rollover and leap days', () => {
  assert.deepEqual(getRechargeDateBounds(new Date('2026-12-31T16:30:00Z')), {
    today: '2027-01-01',
    minDate: '2027-01-02',
    defaultDate: '2027-01-04'
  })
  assert.deepEqual(getRechargeDateBounds(new Date('2028-02-28T01:00:00Z')), {
    today: '2028-02-28',
    minDate: '2028-02-29',
    defaultDate: '2028-03-02'
  })
})

test('manual submission rejects malformed or impossible dates', () => {
  const now = new Date('2026-02-01T01:00:00Z')
  for (const value of [
    '',
    null,
    undefined,
    'invalid',
    '2026-02-30',
    '2026-2-2',
    '2026-02-02T00:00:00Z'
  ]) {
    assert.equal(isValidRechargeExpectedDate(value, now), false)
  }
})

test('an open dialog revalidates its date after Beijing midnight', () => {
  const beforeMidnight = new Date('2026-10-12T15:59:00Z')
  const afterMidnight = new Date('2026-10-12T16:00:00Z')
  assert.equal(isValidRechargeExpectedDate('2026-10-13', beforeMidnight), true)
  assert.equal(isValidRechargeExpectedDate('2026-10-13', afterMidnight), false)
})
