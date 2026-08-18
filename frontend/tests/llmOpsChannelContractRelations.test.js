import assert from 'node:assert/strict'
import test from 'node:test'

import {
  currentContractVersion,
  futureContractVersion,
  offeringsForModel
} from '../src/utils/channelContractRelations.js'

test('relation overview keeps every offering linked through versions or prices', () => {
  const result = offeringsForModel({
    offerings: [
      { id: 1, model: 10 },
      { id: 2, model: null },
      { id: 3, model: 20 }
    ],
    versions: [{ offering: 2, model: 10 }],
    priceItems: [],
    modelId: 10
  })

  assert.deepEqual(
    result.map((offering) => offering.id),
    [1, 2]
  )
})

test('current and future contracts use business effective boundaries', () => {
  const now = new Date('2026-08-18T00:00:00Z').getTime()
  const versions = [
    {
      offering: 1,
      version: 1,
      status: 'active',
      effective_from: '2026-08-17T00:00:00Z',
      effective_to: '2026-08-19T00:00:00Z'
    },
    {
      offering: 1,
      version: 2,
      status: 'scheduled',
      effective_from: '2026-08-19T00:00:00Z',
      effective_to: null
    }
  ]

  assert.equal(currentContractVersion(versions, 1, now).version, 1)
  assert.equal(futureContractVersion(versions, 1, now).version, 2)
})
