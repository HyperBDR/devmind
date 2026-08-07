import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { baseCompile } from '@intlify/message-compiler'

const localeFiles = ['en.json', 'zh-CN.json']

function readMetadataPlaceholder(localeFile) {
  const locale = JSON.parse(
    readFileSync(
      new URL(`../src/locales/${localeFile}`, import.meta.url),
      'utf8'
    )
  )
  return locale.llmOps.resalePlatformModal.placeholders.metadata
}

function compileStrictly(message) {
  return baseCompile(message, {
    onError(error) {
      throw error
    }
  })
}

test('metadata placeholders compile in every supported locale', () => {
  for (const localeFile of localeFiles) {
    assert.doesNotThrow(() => {
      compileStrictly(readMetadataPlaceholder(localeFile))
    }, localeFile)
  }
})
