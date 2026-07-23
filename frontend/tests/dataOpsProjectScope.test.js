import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isDomesticProject,
  isOverseasProject,
  projectBusinessScope
} from '../src/utils/dataOpsProjectScope.js'

test('prefers the business scope label over the source scope', () => {
  const project = {
    domestic_type: '纯海外项目',
    project_scope: 'domestic'
  }

  assert.equal(projectBusinessScope(project), 'overseas')
  assert.equal(isDomesticProject(project), false)
  assert.equal(isOverseasProject(project), true)
})

test('treats overseas-to-domestic work as overseas-related business', () => {
  assert.equal(
    projectBusinessScope({ domestic_type: '海外转国内' }),
    'overseas'
  )
})

test('falls back to the normalized source scope', () => {
  assert.equal(projectBusinessScope({ project_scope: 'domestic' }), 'domestic')
  assert.equal(projectBusinessScope({ project_scope: 'overseas' }), 'overseas')
})
