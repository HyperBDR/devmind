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

test('the backend worker includes LibreOffice and consumes quotation queues', () => {
  const queues = [
    'backend',
    'quotation_sync',
    'quotation_excel',
    'quotation_pdf',
    'quotation_render',
  ].join(',')

  for (const source of [compose, devCompose]) {
    assert.match(
      source,
      new RegExp(
        `backend-worker:[\\s\\S]*?target: backend-render[\\s\\S]*?CELERY_QUEUES: ${queues}`,
      ),
    )
    assert.doesNotMatch(source, /quotation-render-worker:/)
    assert.doesNotMatch(source, /quotation-excel-worker:/)
    assert.doesNotMatch(source, /quotation-pdf-worker:/)
    assert.doesNotMatch(source, /gotenberg:/)
  }
})

test('document parser queues remain declared', () => {
  for (const queue of ['quotation_excel', 'quotation_pdf']) {
    assert.match(celerySettings, new RegExp(`Queue\\("${queue}"`))
  }
})

test('deployment tools manage only the consolidated backend worker', () => {
  for (const source of [installScript, controlScript]) {
    assert.match(source, /backend-worker/)
    assert.doesNotMatch(source, /quotation-excel-worker/)
    assert.doesNotMatch(source, /quotation-pdf-worker/)
    assert.doesNotMatch(source, /quotation-render-worker/)
  }
})
