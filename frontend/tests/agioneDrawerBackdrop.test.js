import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createDialogBackdropDismiss, isDialogBackdropPointer } from '../src/utils/agioneDialog.js'

function fixture() {
  let closed = 0
  const dialog = { open: true, getBoundingClientRect: () => ({ left: 480, right: 1440, top: 0, bottom: 1100 }) }
  const handler = createDialogBackdropDismiss(() => { closed++ })
  const event = (x = 120, y = 300, target = dialog, extra = {}) => ({ currentTarget: dialog, target, clientX: x, clientY: y, button: 0, isPrimary: true, preventDefault() {}, ...extra })
  return { dialog, handler, event, count: () => closed }
}

test('a primary backdrop click dismisses the drawer', () => {
  const f = fixture()
  f.handler.onPointerDown(f.event())
  f.handler.onClick(f.event())
  assert.equal(f.count(), 1)
})

test('drawer content and dialog padding do not dismiss', () => {
  const f = fixture()
  for (const target of [f.dialog, {}]) {
    f.handler.onPointerDown(f.event(600, 200, target))
    f.handler.onClick(f.event(600, 200, target))
  }
  assert.equal(f.count(), 0)
})

test('dragging from inside to backdrop or the reverse does not dismiss', () => {
  const f = fixture()
  f.handler.onPointerDown(f.event(600))
  f.handler.onClick(f.event(100))
  f.handler.onPointerDown(f.event(100))
  f.handler.onClick(f.event(600))
  assert.equal(f.count(), 0)
})

test('keyboard clicks, non-primary pointers and secondary buttons do not dismiss', () => {
  const f = fixture()
  f.handler.onClick(f.event())
  for (const extra of [{ button: 2 }, { isPrimary: false }]) {
    f.handler.onPointerDown(f.event(100, 200, f.dialog, extra))
    f.handler.onClick(f.event())
  }
  assert.equal(f.count(), 0)
})

test('cancel or close resets a pending backdrop click', () => {
  const f = fixture()
  f.handler.onPointerDown(f.event())
  f.handler.reset()
  f.handler.onClick(f.event())
  assert.equal(f.count(), 0)
})

test('closed dialogs and non-finite pointer positions are not backdrop hits', () => {
  const f = fixture()
  assert.equal(isDialogBackdropPointer(f.event(NaN)), false)
  f.dialog.open = false
  assert.equal(isDialogBackdropPointer(f.event()), false)
})

test('a new open dialog does not inherit an old pointer gesture', () => {
  const f = fixture()
  f.handler.onPointerDown(f.event())
  const other = { ...f.dialog }
  f.handler.onClick(f.event(100, 200, other, { currentTarget: other }))
  assert.equal(f.count(), 0)
})

test('scoping must not move the html scroll lock onto the sticky sidebar ancestor', () => {
  const css = readFileSync(new URL('../src/components/agione-demo/demo-scoped.css', import.meta.url), 'utf8')
  assert.doesNotMatch(css, /\.agione-demo:has\(#dialog\.request-drawer\[open\]\)\s*\{[^}]*overflow\s*:/)
  const page = readFileSync(new URL('../src/pages/AgioneOps.vue', import.meta.url), 'utf8')
  assert.match(page, /html\.agione-drawer-open\s*\{[^}]*overflow:\s*hidden/)
})

test('drawer routes backdrop and cancellation through the same controller close', () => {
  const code = readFileSync(new URL('../src/components/agione-demo/RequestDrawer.vue', import.meta.url), 'utf8')
  assert.match(code, /@pointerdown="backdrop\.onPointerDown"/)
  assert.match(code, /@click="backdrop\.onClick"/)
  assert.match(code, /@pointercancel="backdrop\.reset"/)
  assert.match(code, /@cancel\.prevent="\$emit\('close'\)"/)
  assert.match(code, /createDialogBackdropDismiss\(\(\)=>emit\('close'\)\)/)
})
