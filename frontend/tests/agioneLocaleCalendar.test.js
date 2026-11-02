import test from 'node:test'
import assert from 'node:assert/strict'
import { calendarMonth } from '../src/components/agione-demo/core.mjs'

test('English calendar uses a readable month name without changing date values', () => {
  const english = calendarMonth('2026-10', 'en')
  const chinese = calendarMonth('2026-10', 'zh-CN')
  assert.equal(english.title, 'October 2026')
  assert.equal(chinese.title, '2026年10月')
  assert.deepEqual(english.days, chinese.days)
  assert.equal(english.days.length, 42)
  assert.equal(english.days[3], '2026-10-01')
})

test('calendar language is explicit and does not leak between renders', () => {
  assert.equal(calendarMonth('2026-12', 'en-GB').title, 'December 2026')
  assert.equal(calendarMonth('2026-12').title, '2026年12月')
  assert.equal(calendarMonth('2027-01', 'en-US').title, 'January 2027')
})
