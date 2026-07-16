import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const files = [
  'src/modules/quotation/App.vue',
  'src/modules/quotation/pages/QuotationListPage.vue',
  'src/modules/quotation/pages/QuotationDetailPage.vue',
]

function feishuLinkOnlyBranch(source) {
  const marker = 'if (isFeishuLinkOnlyUpdate(updatedFields)) {'
  const start = source.indexOf(marker)
  assert.notEqual(start, -1, 'missing Feishu-link-only update branch')

  let depth = 0
  for (let index = start; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1
    if (source[index] === '}') {
      depth -= 1
      if (depth === 0) {
        return source.slice(start, index + 1)
      }
    }
  }
  throw new Error('unterminated Feishu-link-only update branch')
}

test('clearing stale Feishu links does not immediately reload stale quote data', () => {
  for (const file of files) {
    const source = readFileSync(new URL(`../${file}`, import.meta.url), 'utf8')
    const branch = feishuLinkOnlyBranch(source)

    assert.doesNotMatch(
      branch,
      /\b(?:load|refreshQuotations)\s*\(/,
      `${file} should keep the local cleared button state instead of reloading`,
    )
  }
})
