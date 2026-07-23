import { readdirSync, readFileSync, statSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

function readFilesRecursively(directory, extensions = ['.vue', '.css']) {
  return readdirSync(directory)
    .flatMap((entry) => {
      const path = new URL(`${entry}`, directory)
      const stats = statSync(path)
      if (stats.isDirectory()) {
        return readFilesRecursively(new URL(`${entry}/`, directory), extensions)
      }
      if (extensions.some((extension) => entry.endsWith(extension))) {
        return readFileSync(path, 'utf8')
      }
      return []
    })
    .join('\n')
}

const sidebar = readFileSync(
  new URL('../src/components/layout/AppSidebar.vue', import.meta.url),
  'utf8',
)
const quoteDeskLogo = readFileSync(
  new URL('../src/assets/quote-desk-logo.svg', import.meta.url),
  'utf8',
)
const quotationStyle = readFileSync(
  new URL('../src/modules/quotation/style.css', import.meta.url),
  'utf8',
)
const quotationSources = readFilesRecursively(
  new URL('../src/modules/quotation/', import.meta.url),
)

const oldPurplePalette = /#(?:7559f5|5c43ed|8b7bff|6755f5|4c35d9|6250ea|b2a9f8|c9c2ff)/i

test('Quote Desk branding uses blue and teal instead of the old purple palette', () => {
  assert.match(quoteDeskLogo, /#2563eb/i)
  assert.match(quoteDeskLogo, /#14b8a6/i)
  assert.doesNotMatch(quoteDeskLogo, oldPurplePalette)
  assert.match(sidebar, /background-color:\s*#2563eb/i)
  assert.doesNotMatch(sidebar, /linear-gradient/i)
})

test('Quote Desk logo uses the QD monogram direction', () => {
  assert.match(quoteDeskLogo, /QD monogram/i)
  assert.match(quoteDeskLogo, /rect x="20" y="20" width="216" height="216"/)
  assert.match(quoteDeskLogo, /cx="128" cy="124" r="64"/)
  assert.match(quoteDeskLogo, /d="M107 106h46M107 130h34"/)
  assert.match(quoteDeskLogo, /d="M160 160l31 31"/)
  assert.doesNotMatch(quoteDeskLogo, /d="M82 58h67l31 31/)
})

test('Quote Desk primary buttons use a solid brand color', () => {
  assert.doesNotMatch(quotationStyle, /linear-gradient/i)
  assert.match(
    quotationStyle,
    /\.dm-btn-primary\s*\{[\s\S]*background-color:\s*var\(--dm-primary\)/,
  )
  assert.match(
    quotationStyle,
    /\.dm-btn-primary:hover\s*\{[\s\S]*background-color:\s*var\(--dm-primary-hover\)/,
  )
  assert.doesNotMatch(quotationSources, /\bbg-blue-600\b/)
  assert.doesNotMatch(quotationSources, /\bhover:bg-blue-700\b/)
  assert.match(quotationSources, /text-blue-700/)
})
