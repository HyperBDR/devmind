import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  buildQuickPrompts,
  selectFollowUpQuestions,
  splitFollowUpQuestions
} from '../src/utils/aiSuggestions.js'

const assistantSection = readFileSync(
  new URL('../src/components/data-ops/AiAssistantSection.vue', import.meta.url),
  'utf8'
)
const aiMessage = readFileSync(
  new URL('../src/components/data-ops/DataOpsAiMessage.vue', import.meta.url),
  'utf8'
)

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

test('selects fallback suggestions from the matching prompt group', () => {
  const groups = [
    {
      key: 'daily_review',
      questions: ['今天有哪些风险？', '整体经营健康度如何？']
    },
    {
      key: 'pipeline',
      questions: ['哪些立项最值得推进？', 'Pipeline 转化卡在哪里？']
    }
  ]

  assert.deepEqual(selectFollowUpQuestions('请分析 Pipeline 转化', groups), [
    '哪些立项最值得推进？',
    'Pipeline 转化卡在哪里？'
  ])
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

test('renders categorized presets and direct-send follow-up actions', () => {
  assert.match(assistantSection, /prompt\.groupTitle/)
  assert.match(assistantSection, /@click="\$emit\('ask', prompt\.question\)"/)
  assert.match(assistantSection, /:fallback-suggestions="/)
  assert.match(aiMessage, /dataOps\.ai\.followUpsTitle/)
  assert.match(aiMessage, /@click="\$emit\('ask', question\)"/)
  assert.match(aiMessage, /status\.value === 'done'/)
})

test('opens an empty conversation at the top of its prompt list', () => {
  assert.match(
    assistantSection,
    /messagesEl\.value\.scrollTop\s*=\s*isEmptyConversation\.value\s*\?\s*0/
  )
})

test('anchors a follow-up question near the top quarter while streaming', () => {
  assert.match(assistantSection, /v-if="loading"[\s\S]*data-ops-stream-reserve/)
  assert.match(
    assistantSection,
    /latestUserTop\s*-\s*messagesEl\.value\.clientHeight\s*\*\s*0\.25/
  )
  assert.match(assistantSection, /keepStreamingAnswerVisible/)
  assert.doesNotMatch(
    assistantSection,
    /lastMessageContent\.value,[\s\S]*\(\)\s*=>\s*scrollToBottom\(\)/
  )
})
