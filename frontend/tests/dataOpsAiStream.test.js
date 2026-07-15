import assert from 'node:assert/strict'
import test from 'node:test'

import {
  appendAiContent,
  readDataOpsSseResponse,
  resolveFinalAiContent
} from '../src/utils/dataOpsAiStream.js'

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
