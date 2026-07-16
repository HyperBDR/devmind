import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const versionDiff = readFileSync(
  new URL('../src/modules/quotation/utils/versionDiff.ts', import.meta.url),
  'utf8',
)
const details = readFileSync(
  new URL('../src/modules/quotation/components/QuotationDetails.vue', import.meta.url),
  'utf8',
)
const preview = readFileSync(
  new URL('../src/modules/quotation/components/QuotationPreview.vue', import.meta.url),
  'utf8',
)
const english = JSON.parse(
  readFileSync(new URL('../src/modules/quotation/locales/en.json', import.meta.url), 'utf8'),
)

test('historical notes are included in version comparison', () => {
  assert.match(versionDiff, /\| 'remarksDisclaimer'/)
  assert.match(versionDiff, /\['remarksDisclaimer', normalizeText\(version\.remarksDisclaimer\)\]/)
  assert.match(versionDiff, /remarksDisclaimer: normalizeText\(current\.remarksDisclaimer\)/)
})

test('historical notes use their own value and are highlighted when changed', () => {
  assert.match(details, /remarksDisclaimer: ver\.remarksDisclaimer \?\? q\.remarksDisclaimer/)
  assert.match(
    preview,
    /isHeaderChanged\('remarksDisclaimer'\)\s*\? 'bg-rose-50 text-rose-700 font-semibold'\s*:\s*'bg-slate-50 text-slate-700'/,
  )
  assert.equal(
    english.quotation.pages.details.diffFieldRemarksDisclaimer,
    'Notes & disclaimers',
  )
})
