import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildQuickPrompts,
  resolveAssistantQuestionGroups,
  resolveQuickPromptLimit,
  splitFollowUpQuestions
} from '../src/utils/aiSuggestions.js'
import { relativizeSameOriginUrls } from '../src/utils/markdownLinks.js'

test('extracts clickable next-round questions from an AI answer', () => {
  const result = splitFollowUpQuestions(`经营风险总体可控。

建议追问：
- 哪些合同需要本周优先处理？
- 可以按负责人列出跟进顺序吗？
- 最近一次同步后有哪些数据变化？`)

  assert.equal(result.body, '经营风险总体可控。')
  assert.deepEqual(result.questions, [
    '哪些合同需要本周优先处理？',
    '可以按负责人列出跟进顺序吗？',
    '最近一次同步后有哪些数据变化？'
  ])
})

test('extracts English follow-up questions from an AI answer', () => {
  const result = splitFollowUpQuestions(`Collection risk is concentrated.

Suggested follow-up questions:
- Which owners need immediate follow-up?
- Which contracts expire this month?`)

  assert.equal(result.body, 'Collection risk is concentrated.')
  assert.deepEqual(result.questions, [
    'Which owners need immediate follow-up?',
    'Which contracts expire this month?'
  ])
})

test('keeps the full answer when it has no suggestion marker', () => {
  const content = '当前没有足够数据，建议先完成数据同步。'

  assert.deepEqual(splitFollowUpQuestions(content), {
    body: content,
    questions: []
  })
})

test('balances preset prompts across business question groups', () => {
  const prompts = buildQuickPrompts(
    [
      { key: 'daily', title: '日常', questions: ['日常 1', '日常 2'] },
      { key: 'cash', title: '回款', questions: ['回款 1', '回款 2'] },
      { key: 'quality', title: '质量', questions: ['质量 1'] }
    ],
    4
  )

  assert.deepEqual(
    prompts.map((item) => item.groupKey),
    ['daily', 'cash', 'quality', 'daily']
  )
})

test('uses app-owned question groups when no locale override exists', () => {
  const groups = resolveAssistantQuestionGroups(
    [
      {
        key: 'operations',
        title: '运营待办',
        questions: ['哪些运营模型需要处理？']
      }
    ],
    {}
  )

  assert.deepEqual(groups, [
    {
      key: 'operations',
      title: '运营待办',
      questions: ['哪些运营模型需要处理？']
    }
  ])
})

test('prefers localized question groups for matching app group keys', () => {
  const groups = resolveAssistantQuestionGroups(
    [{ key: 'daily_review', title: 'Backend', questions: ['Backend?'] }],
    {
      daily_review: {
        title: 'Localized',
        questions: ['Localized?']
      }
    }
  )

  assert.equal(groups[0].title, 'Localized')
  assert.deepEqual(groups[0].questions, ['Localized?'])
})

test('uses an app-owned quick question limit with safe bounds', () => {
  assert.equal(resolveQuickPromptLimit(8), 8)
  assert.equal(resolveQuickPromptLimit(99), 12)
  assert.equal(resolveQuickPromptLimit('invalid'), 6)
})

test('converts same-origin assistant URLs to relative paths', () => {
  const content = [
    '[进入工作台](http://localhost:8000/llm-ops?section=reseller)',
    '当前页：http://localhost:8000/llm-ops?section=monitor',
    '[外部文档](https://example.com/docs)'
  ].join('\n')

  assert.equal(
    relativizeSameOriginUrls(content, 'http://localhost:8000'),
    [
      '[进入工作台](/llm-ops?section=reseller)',
      '当前页：/llm-ops?section=monitor',
      '[外部文档](https://example.com/docs)'
    ].join('\n')
  )
})
