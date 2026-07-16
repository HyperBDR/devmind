import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  appendAiContent,
  readDataOpsSseResponse,
  resolveFinalAiContent
} from '../src/utils/dataOpsAiStream.js'
import { localizeDataOpsProgressEvent } from '../src/utils/dataOpsProgress.js'

const enLocale = JSON.parse(
  readFileSync(
    new URL('../src/locales/data-ops/en.json', import.meta.url),
    'utf8'
  )
)
const zhLocale = JSON.parse(
  readFileSync(
    new URL('../src/locales/data-ops/zh-CN.json', import.meta.url),
    'utf8'
  )
)

function translateProgress(locale, key, values = {}) {
  const leaf = key
    .replace('dataOps.feedback.progress.', '')
    .split('.')
    .reduce((value, part) => value?.[part], locale.feedback.progress)
  return String(leaf || '').replace(/\{(\w+)\}/gu, (_, name) => {
    return values[name] ?? `{${name}}`
  })
}

test('re-localizes stored progress events when the UI language changes', () => {
  const event = {
    stage: 'plan',
    title: '请求模型规划查询',
    detail: '让模型判断需要查询的表、筛选条件、聚合指标和输出形态。'
  }

  const english = localizeDataOpsProgressEvent(event, (key, values) =>
    translateProgress(enLocale, key, values)
  )
  const chinese = localizeDataOpsProgressEvent(event, (key, values) =>
    translateProgress(zhLocale, key, values)
  )

  assert.equal(english.title, 'Plan data queries')
  assert.match(english.detail, /tables, filters, metrics, and output/i)
  assert.equal(chinese.title, '规划数据查询')
  assert.match(chinese.detail, /数据表、筛选条件、指标和输出形式/)
})

test('localizes the reasoning diagnosis progress stage', () => {
  const event = localizeDataOpsProgressEvent(
    { stage: 'reasoning' },
    (key, values) => translateProgress(enLocale, key, values)
  )

  assert.equal(event.title, 'Select root-cause diagnosis')
  assert.match(event.detail, /evidence.*root-cause hypotheses/i)
})

test('describes intent recognition before data planning', () => {
  assert.equal(
    enLocale.feedback.progress.questionTitle,
    'Identify request intent'
  )
  assert.match(
    enLocale.feedback.progress.questionDetail,
    /whether business data is needed/i
  )
})

test('delivers answer chunks before the SSE response finishes', async () => {
  const encoder = new TextEncoder()
  let closeStream
  let firstChunkReceived
  const firstChunk = new Promise((resolve) => {
    firstChunkReceived = resolve
  })
  const response = new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"chunk","content":"第一段"}\r\n\r\n')
        )
        closeStream = () => {
          controller.enqueue(
            encoder.encode(
              'data: {"type":"content","content":"第二段"}\n\n' +
                'data: {"type":"done","reply":"第一段第二段"}\n\n'
            )
          )
          controller.close()
        }
      }
    })
  )
  const chunks = []

  const reading = readDataOpsSseResponse(response, {
    onChunk(content) {
      chunks.push(content)
      firstChunkReceived()
    }
  })

  await firstChunk
  assert.deepEqual(chunks, ['第一段'])

  closeStream()
  await reading
  assert.deepEqual(chunks, ['第一段', '第二段'])
})

test('uses the normalized final answer after streaming completes', () => {
  const streamed = 'Collection risk is concentrated.'
  const finalAnswer = `${streamed}\n\nSuggested follow-up questions:\n- Which owner should act first?\n- Which contracts are affected?`

  assert.equal(
    resolveFinalAiContent(streamed, finalAnswer, 'No answer'),
    finalAnswer
  )
})

test('rejects an SSE response that ends without a terminal event', async () => {
  const encoder = new TextEncoder()
  const response = new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"progress","stage":"answer"}\n\n')
        )
        controller.close()
      }
    })
  )

  await assert.rejects(
    readDataOpsSseResponse(response),
    (error) => error?.code === 'SSE_STREAM_INCOMPLETE'
  )
})

test('uses the empty-answer fallback when only tool markup is returned', () => {
  const rawReply = [
    '<｜｜DSML｜｜tool_calls>',
    '<｜｜DSML｜｜invoke name="data_ops_aggregate">',
    '</｜｜DSML｜｜invoke>',
    '</｜｜DSML｜｜tool_calls>'
  ].join('')

  assert.equal(
    resolveFinalAiContent('', rawReply, '没有可展示的回答'),
    '没有可展示的回答'
  )
})

test('uses the fallback for an unterminated tool block', () => {
  const rawReply = [
    '<｜｜DSML｜｜tool_calls>',
    '<｜｜DSML｜｜invoke name="data_ops_aggregate">'
  ].join('')

  assert.equal(
    resolveFinalAiContent('', rawReply, '没有可展示的回答'),
    '没有可展示的回答'
  )
})

test('keeps partial tool markup until a later chunk can remove it', () => {
  const first = appendAiContent('', '<｜｜DSML｜｜tool_calls>hidden')
  const second = appendAiContent(first, '</｜｜DSML｜｜tool_calls>真实回答')

  assert.equal(second, '真实回答')
})

test('keeps displayable text after removing tool markup', () => {
  const rawReply = [
    '<｜｜DSML｜｜tool_calls>hidden</｜｜DSML｜｜tool_calls>',
    '## 回款健康度\n\n整体风险可控。'
  ].join('')

  assert.equal(
    resolveFinalAiContent('', rawReply, '没有可展示的回答'),
    '## 回款健康度\n\n整体风险可控。'
  )
})
