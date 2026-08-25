import assert from 'node:assert/strict'
import test from 'node:test'

import {
  offeringsForModel
} from '../src/utils/channelContractRelations.js'

test('relation overview keeps every offering linked through current prices', () => {
  const result = offeringsForModel({
    offerings: [
      { id: 1, model: 10 },
      { id: 2, model: null },
      { id: 3, model: 20 }
    ],
    versions: [],
    priceItems: [],
    modelId: 10
  })

  assert.deepEqual(result.map((offering) => offering.id), [1])
})
