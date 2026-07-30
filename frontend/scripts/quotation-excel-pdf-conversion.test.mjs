import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const api = readFileSync(
  new URL('../src/modules/quotation/api/exports.ts', import.meta.url),
  'utf8',
)
const compose = readFileSync(
  new URL('../../docker-compose.yml', import.meta.url),
  'utf8',
)
const devCompose = readFileSync(
  new URL('../../docker-compose.dev.yml', import.meta.url),
  'utf8',
)
const celerySettings = readFileSync(
  new URL('../../backend/core/settings/celery.py', import.meta.url),
  'utf8',
)
const installScript = readFileSync(
  new URL('../../scripts/install.sh', import.meta.url),
  'utf8',
)
const controlScript = readFileSync(
  new URL('../../scripts/devmindctl.sh', import.meta.url),
  'utf8',
)
const quotationList = readFileSync(
  new URL('../src/modules/quotation/components/QuotationList.vue', import.meta.url),
  'utf8',
)
const quotationDetails = readFileSync(
  new URL('../src/modules/quotation/components/QuotationDetails.vue', import.meta.url),
  'utf8',
)

test('quotation exports use the asynchronous backend contract', () => {
  assert.match(api, /\/quotations\/\$\{encodeURIComponent\(quotationId\)\}\/exports/)
  assert.match(api, /\/exports\/\$\{encodeURIComponent\(jobId\)\}/)
  assert.match(api, /status === 'render_failed'/)
  assert.match(api, /status === 'upload_failed'/)
  assert.match(api, /\/retry-upload/)
})

test('quotation export progress and upload-only retry are visible', () => {
  assert.match(api, /onProgress/)
  assert.match(quotationList, /retryQuotationUpload/)
  assert.match(quotationList, /failedUploadByQuote/)
  assert.match(quotationList, /exportProgressByQuote/)
  assert.match(quotationDetails, /activeExportStatus/)
})

test('LibreOffice is isolated to the quotation render worker', () => {
  for (const source of [compose, devCompose]) {
    assert.match(source, /quotation-render-worker:/)
    assert.match(source, /CELERY_QUEUES: quotation_render/)
    assert.doesNotMatch(source, /gotenberg:/)
  }
})

test('document parser queues are declared and have dedicated workers', () => {
  const parserWorkers = [
    ['quotation-excel-worker', 'quotation_excel'],
    ['quotation-pdf-worker', 'quotation_pdf'],
  ]

  for (const [service, queue] of parserWorkers) {
    assert.match(celerySettings, new RegExp(`Queue\\("${queue}"`))
    for (const source of [compose, devCompose]) {
      assert.match(
        source,
        new RegExp(`${service}:[\\s\\S]*?CELERY_QUEUES: ${queue}`),
      )
    }
  }
})

test('deployment tools manage every quotation worker', () => {
  const workers = [
    'quotation-excel-worker',
    'quotation-pdf-worker',
    'quotation-render-worker',
  ]

  for (const worker of workers) {
    assert.match(installScript, new RegExp(worker))
    assert.match(controlScript, new RegExp(worker))
  }
})
