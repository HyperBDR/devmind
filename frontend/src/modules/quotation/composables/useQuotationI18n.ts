import { useI18n } from 'vue-i18n'
import type { QuoteStatus } from '../types'

export function useQuotationI18n() {
  const { t, locale } = useI18n()

  function quoteStatusLabel(status: QuoteStatus): string {
    return t(`quotation.status.${status}`)
  }

  return {
    t,
    locale,
    quoteStatusLabel,
  }
}
