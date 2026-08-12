import {
  ApiError,
  apiRequest,
  getAccessToken,
  getApiBaseUrl,
} from './client'

export type QuotationExportFormat = 'xlsx' | 'pdf'

export type QuotationExportStatus =
  | 'queued'
  | 'rendering_excel'
  | 'converting_pdf'
  | 'rendered'
  | 'upload_queued'
  | 'uploading'
  | 'completed'
  | 'render_failed'
  | 'upload_failed'

export interface QuotationExportAsset {
  id: string
  format: QuotationExportFormat
  file_name: string
  mime_type: string
  size_bytes: number
  content_hash: string
  download_url: string
}

export interface QuotationExportJob {
  job_id: string
  status: QuotationExportStatus
  quotation_id: string
  quotation_version: number
  template_id: string
  template_version: number
  renderer_version: string
  formats: QuotationExportFormat[]
  archive_to_feishu: boolean
  archive_folder_token?: string | null
  error_code?: string | null
  error_message?: string | null
  assets: QuotationExportAsset[]
  created_at: string
  updated_at: string
  finished_at?: string | null
}

interface CreateQuotationExportResponse {
  job_id: string
  status: QuotationExportStatus
}

interface QuotationExportProgressOptions {
  onProgress?: (job: QuotationExportJob) => void
  quotationVersion?: number
  archiveFolderToken?: string
}

const TERMINAL_STATUSES = new Set<QuotationExportStatus>([
  'completed',
  'render_failed',
  'upload_failed',
])

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

export function createQuotationExport(
  quotationId: string,
  formats: QuotationExportFormat[],
  options: {
    quotationVersion?: number
    templateId?: string
    archiveToFeishu?: boolean
    archiveFolderToken?: string
  } = {},
): Promise<CreateQuotationExportResponse> {
  return apiRequest<CreateQuotationExportResponse>(
    `/quotations/${encodeURIComponent(quotationId)}/exports`,
    {
      method: 'POST',
      body: JSON.stringify({
        formats,
        quotation_version: options.quotationVersion,
        template_id: options.templateId,
        archive_to_feishu: options.archiveToFeishu ?? false,
        archive_folder_token: options.archiveFolderToken || undefined,
      }),
    },
  )
}

export function getQuotationExport(
  jobId: string,
): Promise<QuotationExportJob> {
  return apiRequest<QuotationExportJob>(
    `/exports/${encodeURIComponent(jobId)}`,
  )
}

export function retryQuotationUpload(
  jobId: string,
): Promise<CreateQuotationExportResponse> {
  return apiRequest<CreateQuotationExportResponse>(
    `/exports/${encodeURIComponent(jobId)}/retry-upload`,
    { method: 'POST', body: JSON.stringify({}) },
  )
}

export async function waitForQuotationExport(
  jobId: string,
  options: {
    timeoutMs?: number
    pollMs?: number
    onProgress?: (job: QuotationExportJob) => void
  } = {},
): Promise<QuotationExportJob> {
  const deadline = Date.now() + (options.timeoutMs ?? 600_000)
  const pollMs = options.pollMs ?? 250
  while (Date.now() < deadline) {
    const job = await getQuotationExport(jobId)
    options.onProgress?.(job)
    if (TERMINAL_STATUSES.has(job.status)) return job
    await delay(pollMs)
  }
  throw new ApiError('Quotation export is still processing', 408)
}

export async function downloadQuotationExportAsset(
  asset: QuotationExportAsset,
): Promise<void> {
  const token = getAccessToken()
  const response = await fetch(
    `${getApiBaseUrl()}/documents/${encodeURIComponent(asset.id)}/download`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    },
  )
  if (!response.ok) {
    throw new ApiError(`Download failed (${response.status})`, response.status)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = asset.file_name
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export async function exportQuotationFile(
  quotationId: string,
  format: QuotationExportFormat,
  options: QuotationExportProgressOptions = {},
): Promise<QuotationExportJob> {
  const created = await createQuotationExport(quotationId, [format], {
    quotationVersion: options.quotationVersion,
  })
  const job = await waitForQuotationExport(created.job_id, options)
  if (job.status === 'render_failed') {
    throw new ApiError(job.error_message || 'Quotation rendering failed', 422)
  }
  const asset = job.assets.find((candidate) => candidate.format === format)
  if (!asset) {
    throw new ApiError('Rendered quotation file is unavailable', 502)
  }
  await downloadQuotationExportAsset(asset)
  return job
}

export async function archiveQuotationFile(
  quotationId: string,
  format: QuotationExportFormat,
  options: QuotationExportProgressOptions = {},
): Promise<QuotationExportJob> {
  const created = await createQuotationExport(quotationId, [format], {
    archiveToFeishu: true,
    archiveFolderToken: options.archiveFolderToken,
  })
  const job = await waitForQuotationExport(created.job_id, options)
  if (job.status === 'render_failed') {
    throw new ApiError(job.error_message || 'Quotation rendering failed', 422)
  }
  if (job.status === 'upload_failed') return job
  return job
}
