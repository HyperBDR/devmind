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
    { value: 'Uploaded', label: t('quotation.status.Uploaded') },
    { value: 'Sent', label: t('quotation.status.Sent') },
    { value: 'Accepted', label: t('quotation.status.Accepted') },
    { value: 'Rejected', label: t('quotation.status.Rejected') },
    { value: 'Expired', label: t('quotation.status.Expired') },
    { value: 'Cancelled', label: t('quotation.status.Cancelled') },
  ])

  return {
    t,
    locale,
    quoteStatusLabel,
    statusFilterOptions,
  }
}
