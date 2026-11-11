import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildDescriptionHistoryOptions,
  stripDescriptionLabel,
  upsertDescriptionsToCatalog,
} from '../src/modules/quotation/utils/descriptionCatalog.ts'

const yearly = 'License Type: HyperBDR Yearly License. VM Quantity: 1. Cost: 420.'
const tier = (range, cost) =>
  `Description: Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: ${range}. Cost: ${cost}.`

test('only the leading label is removed', () => {
  assert.equal(
    stripDescriptionLabel(yearly),
    'HyperBDR Yearly License. VM Quantity: 1. Cost: 420.',
  )
  assert.equal(stripDescriptionLabel('license type : HyperBDR'), 'HyperBDR')
  assert.equal(stripDescriptionLabel('Description：HyperBDR'), 'HyperBDR')
  for (const value of [
    'HyperBDR Yearly License',
    'Extended Description: kept',
    'HyperBDR. License Type: kept',
    'License Type:',
    'Line one\nLine two',
  ]) {
    assert.equal(stripDescriptionLabel(value), value)
  }
})

test('dropdown options drop the label and keep tiers, prices and order', () => {
  const products = [
    { id: 'p1', name: 'HyperBDR Yearly License', listPrice: 420, currency: 'USD', description: yearly },
  ]
  const services = [
    { id: 's1', name: 'Premium', listPrice: 2300, currency: 'USD', description: tier('1 - 25', 2300) },
    { id: 's2', name: 'Premium', listPrice: 90, currency: 'USD', description: tier('26 - 100', 90) },
  ]
  const history = [
    { type: 'Software', description: 'HyperBDR Yearly License. VM Quantity: 1. Cost: 420.', listPrice: 420, currency: 'USD' },
    { type: 'Software', description: 'License Type: Failback License (One-time).\n29VMs x 2 times', listPrice: 14.9, currency: 'USD' },
  ]

  const software = buildDescriptionHistoryOptions('Software', products, services, [], 'USD', history)
  assert.deepEqual(
    software.map((option) => option.value),
    [
      'HyperBDR Yearly License. VM Quantity: 1. Cost: 420.',
      'Failback License (One-time).\n29VMs x 2 times',
    ],
  )
  assert.equal(software[0].label, 'USD 420')
  assert.equal(software[0].meta.listPrice, 420)
  assert.equal(software[0].meta.itemId, 'p1')

  const others = buildDescriptionHistoryOptions('Others', products, services, [], 'USD', [])
  assert.deepEqual(
    others.map((option) => option.value),
    [
      'Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 1 - 25. Cost: 2300.',
      'Remote Product Service - Premium 7*24 (Optional, Yearly). VM Quantity: 26 - 100. Cost: 90.',
    ],
  )
  assert.deepEqual(others.map((option) => option.label), ['USD 2,300', 'USD 90'])
})

test('saving a quote does not duplicate catalog entries that only differ by label', () => {
  const products = [
    { id: 'p1', name: 'Yearly', listPrice: 420, currency: 'USD', description: yearly },
  ]
  const result = upsertDescriptionsToCatalog(
    [
      { id: 'i1', type: 'Software', description: 'HyperBDR Yearly License. VM Quantity: 1. Cost: 420.', listPrice: 420 },
      { id: 'i2', type: 'Software', description: 'License Type: Brand New License', listPrice: 10 },
    ],
    products,
    [],
  )
  assert.equal(result.added, 1)
  assert.equal(result.products[0], products[0])
  assert.equal(result.products[1].description, 'Brand New License')
  assert.equal(result.products[1].listPrice, 10)
})
