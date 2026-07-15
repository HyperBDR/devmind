import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

const dataOpsPage = readFileSync(
  new URL('../src/pages/DataOps.vue', import.meta.url),
  'utf8'
)
const dataOpsConsole = readFileSync(
  new URL('../src/composables/useDataOpsConsole.js', import.meta.url),
  'utf8'
)
const dataOpsApi = readFileSync(
  new URL('../src/api/dataOps.js', import.meta.url),
  'utf8'
)

test('does not expose or preload the retired kanban view', () => {
  assert.doesNotMatch(dataOpsPage, /KanbanSection|key: 'kanban'/)
  assert.doesNotMatch(dataOpsConsole, /loadKanban|kanbanContracts/)
  assert.doesNotMatch(
    dataOpsApi,
    /kanban(?:Contracts|Oversea|Project|Domestic|\()/
  )
  assert.equal(
    existsSync(
      new URL('../src/components/data-ops/KanbanSection.vue', import.meta.url)
    ),
    false
  )
  assert.equal(
    existsSync(
      new URL('../src/components/data-ops/KanbanBoard.vue', import.meta.url)
    ),
    false
  )
})
