import type { Quotation } from '../types'

const FEISHU_WEB_ORIGIN = 'https://feishu.cn'
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{10,}$/

function buildDriveFileUrl(token: string): string {
  return `${FEISHU_WEB_ORIGIN}/file/${encodeURIComponent(token)}`
}

export function normalizeFeishuOpenUrl(raw?: string | null): string {
  const value = (raw || '').trim()
  if (!value) return ''

  if (TOKEN_PATTERN.test(value)) {
    return buildDriveFileUrl(value)
  }

  if (/^https?:\/\//i.test(value)) {
    try {
      const url = new URL(value)
      return url.toString()
    } catch {
      return ''
    }
  }

  if (value.startsWith('/')) {
    return `${FEISHU_WEB_ORIGIN}${value}`
  }

  return `${FEISHU_WEB_ORIGIN}/${value.replace(/^\/+/, '')}`
}

export function buildFeishuOpenUrl(quote: Pick<Quotation, 'feishuUrl' | 'feishuFileToken'>): string {
  return normalizeFeishuOpenUrl(quote.feishuUrl) || normalizeFeishuOpenUrl(quote.feishuFileToken)
}
