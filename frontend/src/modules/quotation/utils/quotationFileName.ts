import type { Quotation } from '../types'

/**
 * Sanitize a string for use as a download / Feishu file name.
 */
export function sanitizeExportFileName(name: string): string {
  const cleaned = String(name || '')
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[. ]+$/g, '')
  return cleaned.slice(0, 120) || 'quotation'
}

/**
 * Prefer project name; fall back to quote number.
 */
export function buildQuotationExportBaseName(
  quote: Pick<Quotation, 'projectName' | 'quoteNo'>,
): string {
  const project = (quote.projectName || '').trim()
  const quoteNo = (quote.quoteNo || '').trim()
  return sanitizeExportFileName(project || quoteNo || 'quotation')
}

export function buildQuotationExportFileName(
  quote: Pick<Quotation, 'projectName' | 'quoteNo'>,
  extension: 'pdf' | 'xlsx',
): string {
  const ext = extension.startsWith('.') ? extension.slice(1) : extension
  return `${buildQuotationExportBaseName(quote)}.${ext}`
}
