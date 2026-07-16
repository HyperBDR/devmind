const incompleteStreamCode = 'SSE_STREAM_INCOMPLETE'

export async function readDataOpsSseResponse(response, callbacks = {}) {
  if (!response.body?.getReader) {
    throw streamError('Streaming response body is unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let terminalEvent = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n\r?\n/)
    buffer = parts.pop() || ''
    for (const part of parts) {
      terminalEvent ||= handleSsePart(part, callbacks)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    terminalEvent ||= handleSsePart(buffer, callbacks)
  }
  if (!terminalEvent) {
    throw streamError('AI response stream ended before completion')
  }
  return terminalEvent
}

export function resolveFinalAiContent(currentContent, finalContent, fallback) {
  const current = sanitizeAiContent(currentContent)
  const final = sanitizeAiContent(finalContent)
  return final || current || fallback
}

export function appendAiContent(currentContent, nextContent) {
  return stripCompleteToolBlocks(
    `${currentContent || ''}${nextContent || ''}`
  ).trimStart()
}

export function sanitizeAiContent(content) {
  return stripCompleteToolBlocks(content)
    .replace(/<｜｜DSML｜｜tool_calls>[\s\S]*$/g, '')
    .replace(/&lt;｜｜DSML｜｜tool_calls&gt;[\s\S]*$/g, '')
    .trimStart()
}

function stripCompleteToolBlocks(content) {
  return String(content || '')
    .replace(/<｜｜DSML｜｜tool_calls>[\s\S]*?<\/｜｜DSML｜｜tool_calls>/g, '')
    .replace(
      /&lt;｜｜DSML｜｜tool_calls&gt;[\s\S]*?&lt;\/｜｜DSML｜｜tool_calls&gt;/g,
      ''
    )
}

function handleSsePart(part, callbacks) {
  const data = part
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!data) return ''

  try {
    const payload = JSON.parse(data)
    if (
      (payload.type === 'chunk' || payload.type === 'content') &&
      payload.content != null
    ) {
      callbacks.onChunk?.(payload.content)
    } else if (payload.type === 'progress') {
      callbacks.onProgress?.(payload)
    } else if (payload.type === 'done') {
      callbacks.onDone?.(payload)
      return 'done'
    } else if (payload.type === 'error') {
      callbacks.onError?.(payload.detail || 'Stream error')
      return 'error'
    }
  } catch (_) {
    return ''
  }
  return ''
}

function streamError(message) {
  const error = new Error(message)
  error.code = incompleteStreamCode
  return error
}
