import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { QuoteStatus } from '../types'

export function useQuotationI18n() {
  const { t, locale } = useI18n()

  function quoteStatusLabel(status: QuoteStatus): string {
    return t(`quotation.status.${status}`)
  }

  const statusFilterOptions = computed(() => [
    { value: 'ALL', label: t('quotation.status.all') },
    { value: 'Draft', label: t('quotation.status.Draft') },
    { value: 'Generated', label: t('quotation.status.Generated') },
  ])

  return {
    t,
    locale,
    quoteStatusLabel,
    statusFilterOptions,
  }
}
