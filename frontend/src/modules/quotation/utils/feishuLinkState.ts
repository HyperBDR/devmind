import type { Quotation } from '../types'
import {
  batchCheckFeishuFileAccess,
  getFeishuStatus,
  type FeishuFileAccessBatchItem,
} from '../api/feishu'

const FEISHU_LINK_KEYS = [
  'feishuExcelFileToken',
  'feishuExcelUrl',
  'feishuExcelPath',
  'feishuExcelUploadedAt',
  'feishuPdfFileToken',
  'feishuPdfUrl',
  'feishuPdfPath',
  'feishuPdfUploadedAt',
  'feishuFileToken',
  'feishuUrl',
  'feishuPath',
  'feishuUploadedAt',
] as const

/**
 * Whether an update only clears or adjusts Feishu open-link fields.
 */
export function isFeishuLinkOnlyUpdate(
  fields: Partial<Quotation>,
): boolean {
  const keys = Object.keys(fields)
  return (
    keys.length > 0 &&
    keys.every((key) =>
      (FEISHU_LINK_KEYS as readonly string[]).includes(key),
    )
  )
}

/**
 * Local quote fields to drop after Feishu confirms a file is gone.
 */
export function clearedFeishuFields(
  format: 'excel' | 'pdf',
): Partial<Quotation> {
  if (format === 'excel') {
    return {
      feishuExcelFileToken: undefined,
      feishuExcelUrl: undefined,
      feishuExcelPath: undefined,
      feishuExcelUploadedAt: undefined,
    }
  }
  return {
    feishuPdfFileToken: undefined,
    feishuPdfUrl: undefined,
    feishuPdfPath: undefined,
    feishuPdfUploadedAt: undefined,
  }
}

function buildQuotationFeishuBatchItems(
  quotations: Quotation[],
): FeishuFileAccessBatchItem[] {
  const items: FeishuFileAccessBatchItem[] = []
  for (const quote of quotations) {
    if (quote.feishuExcelFileToken) {
      items.push({
        file_token: quote.feishuExcelFileToken,
        quotation_id: quote.id,
        doc_type: 'excel',
      })
    }
    if (quote.feishuPdfFileToken) {
      items.push({
        file_token: quote.feishuPdfFileToken,
        quotation_id: quote.id,
        doc_type: 'pdf',
      })
    }
  }
  return items
}

/**
 * Validate quotation Feishu links and clear stale DB rows when files are gone.
 */
export async function reconcileFeishuQuotationLinks(
  quotations: Quotation[],
): Promise<boolean> {
  const items = buildQuotationFeishuBatchItems(quotations)
  if (!items.length) {
    return false
  }
  try {
    const status = await getFeishuStatus()
    if (!status.connected) {
      return false
    }
    const response = await batchCheckFeishuFileAccess(items)
    return response.results.some((item) => !item.exists)
  } catch {
    return false
  }
}
