import assert from 'node:assert/strict'
import test from 'node:test'

import { checkSpelling, replaceSpellIssue } from '../src/modules/quotation/utils/spellCheck.ts'

test('detects English and Chinese spelling issues', () => {
  const issues = checkSpelling(
    'HyperBDR montly licence 中文错字测試; Pleas review the servce scope',
  )

  assert.deepEqual(
    issues.map(({ word, suggestion, kind }) => ({ word, suggestion, kind })),
    [
      { word: 'montly', suggestion: 'monthly', kind: 'english' },
      { word: '测試', suggestion: '测试', kind: 'chinese' },
      { word: 'Pleas', suggestion: 'please', kind: 'english' },
      { word: 'servce', suggestion: 'service', kind: 'english' },
    ],
  )
})

test('ignores known project terms', () => {
  assert.deepEqual(checkSpelling('HyperBDR Alibaba Feishu Agione OpenAI'), [])
})

test('replaces an issue at its source position', () => {
  const text = 'Pleas review the servce scope，测试错别字'
  const issues = checkSpelling(text)
  const corrected = [...issues].reverse().reduce(
    (current, issue) => replaceSpellIssue(current, issue),
    text,
  )

  assert.equal(corrected, 'Please review the service scope，测试错别字')
})
