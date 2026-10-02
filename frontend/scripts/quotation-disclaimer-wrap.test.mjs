import assert from 'node:assert/strict'
import test from 'node:test'

import { wrapQuotationDisclaimer } from '../src/modules/quotation/utils/quotationDisclaimer.ts'

test('preview disclaimer lines follow the A4 export wrapping', () => {
  const paragraph =
    'The Professional Services scope covers OnePro product-level installation, configuration, and deployment activities only. The customer is responsible for ensuring the target environment is fully prepared prior to implementation, including but not limited to network connectivity, firewall and security policy configuration, required bandwidth, system accessibility, permissions, credentials, and environment readiness.'

  assert.deepEqual(wrapQuotationDisclaimer(paragraph).split('\n'), [
    'The Professional Services scope covers OnePro product-level installation, configuration, and deployment activities only. The customer is responsible for ',
    'ensuring the target environment is fully prepared prior to implementation, including but not limited to network connectivity, firewall and security policy ',
    'configuration, required bandwidth, system accessibility, permissions, credentials, and environment readiness.',
  ])
})

test('preview disclaimer keeps blank lines and wide characters', () => {
  const paragraph = '备注内容 '.repeat(40)
  const wrapped = wrapQuotationDisclaimer(`first\n\n${paragraph}`)

  assert.ok(wrapped.includes('first\n\n'))
  assert.equal(
    wrapped.replaceAll('\n', '').replaceAll(' ', ''),
    `first${paragraph}`.replaceAll(' ', ''),
  )
  assert.ok(wrapped.split('\n').some((line) => line.includes('备注')))
})
