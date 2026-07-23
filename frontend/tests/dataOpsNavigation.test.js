import assert from 'node:assert/strict'
import test from 'node:test'

import {
  dataOpsSectionPath,
  resolveDataOpsSection
} from '../src/utils/dataOpsNavigation.js'

test('resolves only supported Data Ops sections', () => {
  assert.equal(resolveDataOpsSection('pipeline'), 'pipeline')
  assert.equal(resolveDataOpsSection('unknown'), 'executive')
  assert.equal(resolveDataOpsSection(undefined), 'executive')
})

test('builds stable deep links for every Data Ops section', () => {
  assert.equal(dataOpsSectionPath('executive'), '/data-ops')
  assert.equal(dataOpsSectionPath('contracts'), '/data-ops/contracts')
  assert.equal(dataOpsSectionPath('unknown'), '/data-ops')
})
