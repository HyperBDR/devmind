import { computed } from 'vue'

import { formatRoundedPoints } from '@/utils/pointRounding'
import {
  averageMarginRate,
  RESALE_PRICE_DIMENSION_SPECS
} from '@/utils/resalePricing'

export function useAgioneListingDisplay({
  isHiddenRow,
  props,
  selectedRows,
  t,
  visibleListingRows
}) {
  const listingStatusOptions = computed(() => [
    {
      label: t('llmOps.listingBoard.filters.actionable'),
      value: 'actionable'
    },
    { label: t('llmOps.listingBoard.filters.all'), value: 'all' },
    { label: t('llmOps.listingBoard.filters.listed'), value: 'listed' }
  ])

  const platformLabel = computed(
    () =>
      props.agionePlatform?.name || t('llmOps.listingBoard.platformFallback')
  )

  const batchConfirmAction = computed(() => {
    if (!selectedRows.value.length) return ''
    const actions = new Set(
      selectedRows.value
        .filter((row) => !isHiddenRow(row))
        .map((row) => batchConfirmActionForStatus(row.workflow_status))
        .filter(Boolean)
    )
    return actions.size === 1 ? Array.from(actions)[0] : ''
  })

  const batchConfirmLabel = computed(() => {
    return (
      {
        submit: t('llmOps.listingBoard.batch.confirmSubmit'),
        confirm_publish: t('llmOps.listingBoard.batch.confirmPublish'),
        confirm_update: t('llmOps.listingBoard.batch.confirmUpdate'),
        confirm_offline: t('llmOps.listingBoard.batch.confirmOffline')
      }[batchConfirmAction.value] || t('llmOps.listingBoard.batch.confirm')
    )
  })

  const batchConfirmTone = computed(() => actionTone(batchConfirmAction.value))

  const listingKpis = computed(() => {
    const visibleRows = visibleListingRows.value
    const listedRows = visibleRows.filter((row) => row.is_listed)
    const rowMargins = listedRows
      .map((row) => listingUnifiedMarginRate(row))
      .filter((value) => value !== null)
    const avgMargin = rowMargins.length
      ? Number(
          (
            rowMargins.reduce((sum, value) => sum + value, 0) /
            rowMargins.length
          ).toFixed(1)
        )
      : null
    return [
      {
        label: t('llmOps.listingBoard.kpis.availableModels.label'),
        value: visibleRows.length,
        hint: t('llmOps.listingBoard.kpis.availableModels.hint', {
          count: unlistedCount(visibleRows, listedRows)
        }),
        delta: t('llmOps.listingBoard.kpis.availableModels.delta'),
        deltaTone: 'text-slate-400'
      },
      {
        label: t('llmOps.listingBoard.kpis.platforms.label'),
        value: props.platformCount,
        hint: t('llmOps.listingBoard.kpis.platforms.hint'),
        delta: t('llmOps.listingBoard.kpis.platforms.delta'),
        deltaTone: 'text-slate-400'
      },
      {
        label: t('llmOps.listingBoard.kpis.listed.label'),
        value: listedRows.length,
        hint: t('llmOps.listingBoard.kpis.listed.hint'),
        delta:
          listedRows.length > 0
            ? t('llmOps.listingBoard.kpis.listed.activeDelta')
            : t('llmOps.listingBoard.kpis.listed.pendingDelta'),
        deltaTone: listedRows.length > 0 ? 'text-emerald-600' : 'text-amber-600'
      },
      {
        label: t('llmOps.listingBoard.kpis.unlisted.label'),
        value: visibleRows.length - listedRows.length,
        hint: t('llmOps.listingBoard.kpis.unlisted.hint'),
        delta: t('llmOps.listingBoard.kpis.unlisted.delta'),
        deltaTone: 'text-amber-600'
      },
      {
        label: t('llmOps.listingBoard.kpis.averageMargin.label'),
        value: avgMargin !== null ? `${avgMargin}%` : '—',
        hint: t('llmOps.listingBoard.kpis.averageMargin.hint'),
        delta: t('llmOps.listingBoard.kpis.averageMargin.delta'),
        deltaTone: 'text-slate-400'
      }
    ]
  })

  function batchConfirmActionForStatus(status) {
    return (
      {
        draft: 'submit',
        update_draft: 'submit',
        pending_publish: 'confirm_publish',
        pending_update: 'confirm_update',
        pending_offline: 'confirm_offline'
      }[status] || ''
    )
  }

  function actionTone(kind) {
    return (
      {
        submit: 'primary',
        confirm_publish: 'success',
        confirm_update: 'success',
        confirm_offline: 'danger',
        request_offline: 'warn',
        direct_offline: 'danger',
        mark_offline_exception: 'danger',
        delete: 'danger',
        republish: 'primary',
        start_edit: 'default',
        edit: 'default',
        withdraw: 'default',
        abandon_update: 'warn',
        reject_offline: 'default'
      }[kind] || 'default'
    )
  }

  function rowActionIcon(kind) {
    return (
      {
        abandon_update: 'remove',
        confirm_offline: 'powerOff',
        confirm_publish: 'approve',
        confirm_update: 'approve',
        create: 'add',
        delete: 'delete',
        direct_offline: 'powerOff',
        edit: 'edit',
        mark_offline_exception: 'reject',
        reject_offline: 'reject',
        republish: 'submit',
        request_offline: 'offlineRequest',
        start_edit: 'edit',
        submit: 'submit',
        withdraw: 'withdraw'
      }[kind] || 'edit'
    )
  }

  function batchActionClass(tone) {
    return `batch-action-${tone || 'default'}`
  }

  function unlistedCount(visibleRows, listedRows) {
    return visibleRows.length - listedRows.length
  }

  function activeListingChannelLabel(row) {
    const listings = row.active_listings?.length
      ? row.active_listings
      : row.listings || []
    const channelNames = Array.from(
      new Set(listings.map((listing) => listing.channel_name).filter(Boolean))
    )
    if (channelNames.length) return channelNames.join(' / ')
    return (
      row.lowest_option?.channel_name || t('llmOps.listingBoard.supply.none')
    )
  }

  function listingPriceMetrics(row) {
    return RESALE_PRICE_DIMENSION_SPECS.filter((spec) => {
      if (spec.key !== 'cache') return true
      return (
        row.status_listing?.[spec.retailField] ||
        row.lowest_option?.[spec.costField]
      )
    }).map((spec) => ({
      key: spec.key,
      label: spec.label,
      retail: listingAmountText(
        listingDisplayAmount(
          row.status_listing?.[spec.retailField],
          row.status_listing?.currency
        )
      ),
      points: listingPointText(
        row.status_listing?.[spec.retailField],
        row.status_listing?.currency
      ),
      cost: listingAmountText(row.lowest_option?.[spec.costField])
    }))
  }

  function listingAmountText(value) {
    if (value === null || value === undefined || value === '') return '-'
    const amount = Number(value)
    if (!Number.isFinite(amount)) return '-'
    return amount.toFixed(4)
  }

  function listingPointText(value, currency) {
    const amount = Number(value)
    const rate = Number(props.pointConversion?.points_per_currency_unit || 0)
    if (!Number.isFinite(amount) || !Number.isFinite(rate) || rate <= 0) {
      return '-'
    }
    const converted = convertPointCurrencyAmount(
      amount,
      currency,
      props.pointConversion?.currency
    )
    if (converted === null) return '-'
    return formatRoundedPoints(converted * rate, props.pointConversion)
  }

  function listingDisplayAmount(value, currency) {
    return convertPointCurrencyAmount(
      value,
      currency,
      props.displayCurrency || 'CNY'
    )
  }

  function listingCurrency(row) {
    return row.status_listing?.currency || props.displayCurrency || 'CNY'
  }

  function convertPointCurrencyAmount(value, sourceCurrency, targetCurrency) {
    const amount = Number(value)
    if (!Number.isFinite(amount)) return null
    const source = String(
      sourceCurrency || props.displayCurrency || 'CNY'
    ).toUpperCase()
    const target = String(targetCurrency || source).toUpperCase()
    if (source === target) return amount
    const rate = Number(props.exchangeRate || 7.15)
    if (!Number.isFinite(rate) || rate <= 0) return null
    if (source === 'USD' && target === 'CNY') return amount * rate
    if (source === 'CNY' && target === 'USD') return amount / rate
    return null
  }

  function listingUnifiedMarginRate(row) {
    return averageMarginRate(
      RESALE_PRICE_DIMENSION_SPECS.filter((spec) => {
        if (spec.key !== 'cache') return true
        return (
          row.status_listing?.[spec.retailField] ||
          row.lowest_option?.[spec.costField]
        )
      }).map((spec) => ({
        price: listingDisplayAmount(
          row.status_listing?.[spec.retailField],
          row.status_listing?.currency
        ),
        cost: row.lowest_option?.[spec.costField]
      }))
    )
  }

  function normalizeMargin(value) {
    const margin = Number(value)
    if (!Number.isFinite(margin)) return null
    return Number(margin.toFixed(1))
  }

  function platformMarginFloor() {
    const feeRate = Number(props.agionePlatform?.fee_rate)
    const serviceFeeRate = Number(props.agionePlatform?.service_fee_rate)
    const fee = Number.isFinite(feeRate) && feeRate > 0 ? feeRate : 0
    const service =
      Number.isFinite(serviceFeeRate) && serviceFeeRate > 0 ? serviceFeeRate : 0
    return normalizeMargin((fee + service) * 100) ?? 0
  }

  function platformMarginLimit() {
    const limit = Number(props.agionePlatform?.auto_approve_max_margin_rate)
    return Number.isFinite(limit) ? limit : null
  }

  function priceSpecForItemDimension(dimension) {
    return RESALE_PRICE_DIMENSION_SPECS.find(
      (spec) => spec.itemDimension === dimension
    )
  }

  function itemBelongsToRowModel(item, row) {
    const rowModel = row?.model || {}
    const rowMetaModelId = rowModel.meta_model || rowModel.meta_model_id
    if (rowMetaModelId && String(item.meta_model) === String(rowMetaModelId)) {
      return true
    }
    if (String(item.model || '') === String(rowModel.id || '')) return true
    const itemModel = (props.models || []).find(
      (model) => String(model.id) === String(item.model || '')
    )
    return (
      rowMetaModelId &&
      String(itemModel?.meta_model || itemModel?.meta_model_id || '') ===
        String(rowMetaModelId)
    )
  }

  function marketAverageRows(row) {
    const samples = Object.fromEntries(
      RESALE_PRICE_DIMENSION_SPECS.map((spec) => [spec.key, []])
    )
    ;(props.priceItems || []).forEach((item) => {
      if (item.source_is_enabled === false || item.is_current === false) return
      if (!itemBelongsToRowModel(item, row)) return
      const spec = priceSpecForItemDimension(item.dimension)
      if (!spec) return
      const amount = listingDisplayAmount(item.unit_price, item.currency)
      if (amount !== null && amount > 0) samples[spec.key].push(amount)
    })
    RESALE_PRICE_DIMENSION_SPECS.forEach((spec) => {
      if (samples[spec.key].length) return
      ;(row.options || []).forEach((option) => {
        const amount = Number(option[spec.costField])
        if (Number.isFinite(amount) && amount > 0) {
          samples[spec.key].push(amount)
        }
      })
    })
    return RESALE_PRICE_DIMENSION_SPECS.map((spec) => {
      const values = samples[spec.key]
      const average = values.length
        ? values.reduce((sum, value) => sum + value, 0) / values.length
        : null
      const price = listingDisplayAmount(
        row.status_listing?.[spec.retailField],
        row.status_listing?.currency
      )
      return {
        average,
        label: spec.label,
        price
      }
    }).filter(
      (item) =>
        item.price !== null && Number.isFinite(item.average) && item.average > 0
    )
  }

  function priceAboveMarket(row) {
    return marketAverageRows(row).some(
      (item) => Number(item.price) > Number(item.average) + 0.000001
    )
  }

  function marketAverageTitle(row) {
    const rows = marketAverageRows(row).filter(
      (item) => Number(item.price) > Number(item.average) + 0.000001
    )
    if (!rows.length) return ''
    return rows
      .map(
        (item) =>
          `${item.label} ${listingAmountText(item.price)} > ${listingAmountText(
            item.average
          )}`
      )
      .join(' / ')
  }

  function marginToneKey(row) {
    const margin = listingUnifiedMarginRate(row)
    if (margin === null) return 'muted'
    if (priceAboveMarket(row)) return 'high'
    const floor = platformMarginFloor()
    if (margin < floor) return 'low'
    return 'ok'
  }

  function marginPillTone(row) {
    return `margin-pill-${marginToneKey(row)}`
  }

  function marginPillTitle(row) {
    const margin = listingUnifiedMarginRate(row)
    const tone = marginToneKey(row)
    if (tone === 'high') {
      return t('llmOps.listingBoard.marginTone.high', {
        market: marketAverageTitle(row),
        value: formatMarginText(margin)
      })
    }
    return t(`llmOps.listingBoard.marginTone.${tone}`, {
      value: formatMarginText(margin),
      floor: formatMarginText(platformMarginFloor()),
      limit: formatMarginText(platformMarginLimit())
    })
  }

  function formatMarginText(value) {
    const margin = Number(value)
    if (!Number.isFinite(margin)) return '-'
    return `${margin.toFixed(1).replace(/\.0$/, '')}%`
  }

  function statusPillLabel(row) {
    const labels = {
      draft: t('llmOps.listingBoard.workflowStatus.draft'),
      pending_publish: t('llmOps.listingBoard.workflowStatus.pendingPublish'),
      online: t('llmOps.listingBoard.workflowStatus.online'),
      update_draft: t('llmOps.listingBoard.workflowStatus.updateDraft'),
      pending_update: t('llmOps.listingBoard.workflowStatus.pendingUpdate'),
      pending_offline: t('llmOps.listingBoard.workflowStatus.pendingOffline'),
      offline_exception: t(
        'llmOps.listingBoard.workflowStatus.offlineException'
      ),
      offline: t('llmOps.listingBoard.workflowStatus.offline'),
      deleted: t('llmOps.listingBoard.workflowStatus.deleted')
    }
    return (
      labels[row.workflow_status] || t('llmOps.listingBoard.filters.unlisted')
    )
  }

  function statusPillTone(row) {
    if (isHiddenRow(row)) return 'tone-muted'
    if (row.workflow_status === 'online') {
      return 'tone-success'
    }
    if (
      ['pending_publish', 'pending_update', 'pending_offline'].includes(
        row.workflow_status
      )
    )
      return 'tone-warn'
    if (row.workflow_status === 'offline_exception') return 'tone-danger'
    if (['offline', 'deleted'].includes(row.workflow_status)) {
      return 'tone-muted'
    }
    return 'tone-warn'
  }

  function rowStateActions(row) {
    const status = row.workflow_status || 'draft'
    const actions = {
      draft: [
        {
          label: t('llmOps.listingBoard.rowActions.continueEdit'),
          kind: 'edit',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.confirmSubmit'),
          kind: 'submit',
          tone: 'primary'
        },
        {
          label: t('llmOps.listingBoard.rowActions.deleteData'),
          kind: 'delete',
          tone: 'danger'
        }
      ],
      pending_publish: [
        {
          label: t('llmOps.listingBoard.rowActions.withdrawRequest'),
          kind: 'withdraw',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.confirmPublish'),
          kind: 'confirm_publish',
          tone: 'success'
        }
      ],
      online: [
        {
          label: t('llmOps.listingBoard.rowActions.startEdit'),
          kind: 'start_edit',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.requestOffline'),
          kind: 'request_offline',
          tone: 'warn'
        },
        {
          label: t('llmOps.listingBoard.rowActions.directOffline'),
          kind: 'direct_offline',
          tone: 'danger'
        }
      ],
      update_draft: [
        {
          label: t('llmOps.listingBoard.rowActions.continueEdit'),
          kind: 'edit',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.confirmSubmit'),
          kind: 'submit',
          tone: 'primary'
        },
        {
          label: t('llmOps.listingBoard.rowActions.abandonChange'),
          kind: 'abandon_update',
          tone: 'warn'
        }
      ],
      pending_update: [
        {
          label: t('llmOps.listingBoard.rowActions.withdrawChange'),
          kind: 'withdraw',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.confirmUpdate'),
          kind: 'confirm_update',
          tone: 'success'
        }
      ],
      pending_offline: [
        {
          label: t('llmOps.listingBoard.rowActions.withdrawOffline'),
          kind: 'withdraw',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.confirmOffline'),
          kind: 'confirm_offline',
          tone: 'danger'
        },
        {
          label: t('llmOps.listingBoard.rowActions.rejectOffline'),
          kind: 'reject_offline',
          tone: 'default'
        },
        {
          label: t('llmOps.listingBoard.rowActions.markOfflineException'),
          kind: 'mark_offline_exception',
          tone: 'danger'
        }
      ],
      offline_exception: [
        {
          label: t('llmOps.listingBoard.rowActions.confirmOffline'),
          kind: 'confirm_offline',
          tone: 'danger'
        }
      ],
      offline: [
        {
          label: t('llmOps.listingBoard.rowActions.republish'),
          kind: 'republish',
          tone: 'primary'
        },
        {
          label: t('llmOps.listingBoard.rowActions.deleteData'),
          kind: 'delete',
          tone: 'danger'
        }
      ],
      deleted: []
    }
    return (
      actions[status] || [
        {
          label: t('llmOps.listingBoard.rowActions.goListing'),
          kind: 'create',
          tone: 'primary'
        }
      ]
    )
  }

  return {
    batchConfirmAction,
    batchConfirmLabel,
    batchConfirmTone,
    listingKpis,
    listingStatusOptions,
    platformLabel,
    activeListingChannelLabel,
    batchActionClass,
    listingCurrency,
    listingPointText,
    listingPriceMetrics,
    listingUnifiedMarginRate,
    marginPillTitle,
    marginPillTone,
    rowActionIcon,
    rowStateActions,
    statusPillLabel,
    statusPillTone
  }
}
