import test from 'node:test'
import assert from 'node:assert/strict'
import { applyRules } from '../src/components/agione-demo/rules.mjs'
import { customerEvents } from '../src/components/agione-demo/dashboard.mjs'

const customer = {customerTenantId:'1', signals:[], comparisonState:'READY', changePercent:-50,
 inactivity:{state:'READY',daysWithoutCalls:8}, summary:{requestCount:100,unknownCount:0,
 failureCount:4, technicalFailureCount:4, failureClassificationComplete:true}}
const defaults = {inactivityDays:7,declinePercent:40,technicalFailurePercent:2,minTechnicalRequests:20}

test('threshold changes update event and diagnostic lists', () => {
 const data = applyRules({customers:[customer]}, defaults)
 assert.deepEqual(data.customers[0].signals, ['inactive','decline','technical'])
 assert.equal(data.decline.length, 1)
 assert(customerEvents(data.customers)[0].eventKinds.includes('technical'))
 const strict = applyRules({customers:[customer]}, {inactivityDays:9,declinePercent:60,technicalFailurePercent:5,minTechnicalRequests:101})
 assert.deepEqual(strict.customers[0].signals, [])
 assert.equal(strict.decline.length, 0)
})

test('missing previous, status and failure classification never trigger rules', () => {
 const uncertain = {...customer, comparisonState:'UNAVAILABLE', inactivity:{state:'UNAVAILABLE'},
  summary:{...customer.summary, unknownCount:1, failureClassificationComplete:false, technicalFailureCount:null}}
 assert.deepEqual(applyRules({customers:[uncertain]}, defaults).customers[0].signals, [])
})
