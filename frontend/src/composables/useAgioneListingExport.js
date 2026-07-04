import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { exportTableFile } from '@/utils/llmOpsExport'
import { RESALE_PRICE_DIMENSION_SPECS } from '@/utils/resalePricing'

export function useAgioneListingExport({
  activeListingChannelLabel,
  exportableRows,
  listingCurrency,
  listingPointText,
  listingUnifiedMarginRate,
  platformLabel,
  rows,
  statusPillLabel
}) {
  const { t } = useI18n()
  const exportFormat = ref('csv')

  function formatExportAmount(value) {
    if (value === null || value === undefined || value === '') return ''
    const amount = Number(value)
    if (!Number.isFinite(amount)) return ''
    return amount.toFixed(6)
  }

  function formatExportPercent(value) {
    if (value === null || value === undefined || value === '') return ''
    const amount = Number(value)
    if (!Number.isFinite(amount)) return ''
    return `${amount.toFixed(2)}%`
  }

  function exportColumnLabel(key) {
    return t(`llmOps.listingBoard.export.columns.${key}`)
  }

  function exportMetricColumnLabel(spec, key) {
    return t('llmOps.listingBoard.export.metricColumn', {
      metric: spec.label,
      field: exportColumnLabel(key)
    })
  }

  function listingExportColumns() {
    const baseColumns = [
      { key: 'platform', label: exportColumnLabel('platform') },
      { key: 'model', label: exportColumnLabel('model') },
      { key: 'modelCode', label: exportColumnLabel('modelCode') },
      { key: 'metaModel', label: exportColumnLabel('metaModel') },
      { key: 'provider', label: exportColumnLabel('provider') },
      { key: 'channel', label: exportColumnLabel('channel') },
      { key: 'status', label: exportColumnLabel('status') },
      { key: 'currency', label: exportColumnLabel('currency') }
    ]
    const metricColumns = RESALE_PRICE_DIMENSION_SPECS.flatMap((spec) => [
      {
        key: `${spec.key}_cost`,
        label: exportMetricColumnLabel(spec, 'cost')
      },
      {
        key: `${spec.key}_retail`,
        label: exportMetricColumnLabel(spec, 'retail')
      },
      {
        key: `${spec.key}_points`,
        label: exportMetricColumnLabel(spec, 'points')
      }
    ])
    return [
      ...baseColumns,
      ...metricColumns,
      { key: 'margin', label: exportColumnLabel('margin') },
      { key: 'updatedAt', label: exportColumnLabel('updatedAt') }
    ]
  }

  function metricCostValue(row, spec) {
    return formatExportAmount(row.lowest_option?.[spec.costField])
  }

  function metricRetailValue(row, spec) {
    return formatExportAmount(row.status_listing?.[spec.retailField])
  }

  function metricPointValue(row, spec) {
    const points = listingPointText(
      row.status_listing?.[spec.retailField],
      row.status_listing?.currency
    )
    return points === '-' ? '' : points
  }

  function listingExportRecord(row) {
    const listing = row.status_listing || {}
    const record = {
      platform: platformLabel.value,
      model: rows.modelDisplayName(row.model),
      modelCode: row.model?.code || listing.model_code || '',
      metaModel: listing.meta_model_name || row.model?.meta_model_name || '',
      provider: row.provider_name || row.procurement?.provider_name || '',
      channel: listing.channel_name || activeListingChannelLabel(row),
      status: statusPillLabel(row),
      currency: listingCurrency(row),
      margin: formatExportPercent(listingUnifiedMarginRate(row)),
      updatedAt: listing.updated_at || listing.created_at || ''
    }
    RESALE_PRICE_DIMENSION_SPECS.forEach((spec) => {
      record[`${spec.key}_cost`] = metricCostValue(row, spec)
      record[`${spec.key}_retail`] = metricRetailValue(row, spec)
      record[`${spec.key}_points`] = metricPointValue(row, spec)
    })
    return record
  }

  function exportListings() {
    const columns = listingExportColumns()
    const records = exportableRows.value.map(listingExportRecord)
    exportTableFile({
      columns,
      records,
      format: exportFormat.value,
      filenameBase: 'agione-listings'
    })
  }

  return {
    exportFormat,
    exportListings
  }
}
