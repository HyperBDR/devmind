import { h } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatAmount } from '@/composables/useDataOpsConsole'

export const Panel = {
  props: {
    title: { type: String, required: true },
  },
  setup(props, { slots }) {
    return () =>
      h('section', { class: 'rounded-xl border border-slate-200 bg-white' }, [
        h(
          'div',
          { class: 'border-b border-slate-200 px-4 py-3' },
          h('h3', { class: 'text-sm font-bold text-slate-950' }, props.title)
        ),
        h('div', { class: 'p-4' }, slots.default?.()),
      ])
  },
}

export const Toolbar = {
  setup(_, { slots }) {
    return () =>
      h(
        'div',
        {
          class:
            'flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4',
        },
        slots.default?.()
      )
  },
}

export const Kpi = {
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], required: true },
  },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-xl border border-slate-200 bg-white p-4' }, [
        h('p', { class: 'text-xs font-medium text-slate-500' }, props.label),
        h(
          'p',
          { class: 'mt-2 text-2xl font-bold text-slate-950' },
          String(props.value)
        ),
      ])
  },
}

export const DataRow = {
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], required: true },
  },
  setup(props) {
    return () =>
      h('div', { class: 'flex items-start justify-between gap-3 text-sm' }, [
        h('span', { class: 'text-slate-500' }, props.label),
        h('strong', { class: 'text-right text-slate-900' }, String(props.value)),
      ])
  },
}

export const EmptyState = {
  props: {
    text: { type: String, default: '' },
  },
  setup(props) {
    const { t } = useI18n()
    return () =>
      h(
        'div',
        {
          class:
            'rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400',
        },
        props.text || t('dataOps.common.noData')
      )
  },
}

export const MiniList = {
  props: {
    title: { type: String, required: true },
    items: { type: Array, default: () => [] },
    labelKey: { type: String, required: true },
    valueKey: { type: String, required: true },
  },
  setup(props) {
    const { locale, t } = useI18n()
    return () =>
      h('div', [
        h(
          'p',
          { class: 'mb-3 text-xs font-bold uppercase text-slate-500' },
          props.title
        ),
        props.items.length
          ? h(
              'div',
              { class: 'space-y-2' },
              props.items.slice(0, 8).map((item) =>
                h('div', { class: 'flex justify-between gap-3 text-sm' }, [
                  h(
                    'span',
                    { class: 'truncate text-slate-600' },
                    item[props.labelKey] || t('dataOps.common.unknown')
                  ),
                  h(
                    'strong',
                    { class: 'text-slate-900' },
                    formatAmount(item[props.valueKey], '', {
                      locale: locale.value,
                    })
                  ),
                ])
              )
            )
          : h(EmptyState),
      ])
  },
}

export const DataTable = {
  props: {
    columns: { type: Array, required: true },
    rows: { type: Array, default: () => [] },
    emptyText: { type: String, default: '' },
  },
  setup(props) {
    const { t } = useI18n()
    return () =>
      h('div', { class: 'overflow-hidden rounded-xl border border-slate-200 bg-white' }, [
        h('div', { class: 'overflow-x-auto' }, [
          h('table', { class: 'min-w-full divide-y divide-slate-200 text-xs' }, [
            h(
              'thead',
              { class: 'bg-slate-50 text-left font-semibold uppercase text-slate-500' },
              h(
                'tr',
                props.columns.map((col) =>
                  h('th', { class: 'px-4 py-3' }, col.label)
                )
              )
            ),
            h(
              'tbody',
              { class: 'divide-y divide-slate-100 bg-white' },
              props.rows.length
                ? props.rows.map((row) =>
                    h(
                      'tr',
                      { class: 'hover:bg-indigo-50/20' },
                      props.columns.map((col) =>
                        h(
                          'td',
                          { class: 'max-w-[18rem] truncate px-4 py-3 text-slate-700' },
                          col.format
                            ? col.format(row[col.key], row)
                            : row[col.key] || '-'
                        )
                      )
                    )
                  )
                : h('tr', [
                    h(
                      'td',
                      {
                        class: 'px-4 py-10 text-center text-slate-400',
                        colspan: props.columns.length,
                      },
                      props.emptyText || t('dataOps.common.noData')
                    ),
                  ])
            ),
          ]),
        ]),
      ])
  },
}

export const Pager = {
  props: {
    page: { type: Number, required: true },
    total: { type: Number, required: true },
    pageSize: { type: Number, required: true },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n()
    return () => {
      const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize))
      return h('div', { class: 'flex items-center justify-between text-xs text-slate-500' }, [
        h(
          'span',
          t('dataOps.common.totalPages', {
            total: props.total,
            pages: totalPages,
          })
        ),
        h('div', { class: 'flex items-center gap-2' }, [
          h(
            'button',
            {
              class: 'pager-btn',
              disabled: props.page <= 1,
              onClick: () => emit('change', 1),
            },
            t('dataOps.common.firstPage')
          ),
          h(
            'button',
            {
              class: 'pager-btn',
              disabled: props.page <= 1,
              onClick: () => emit('change', props.page - 1),
            },
            t('dataOps.common.previousPage')
          ),
          h(
            'span',
            { class: 'font-semibold text-slate-700' },
            `${props.page} / ${totalPages}`
          ),
          h(
            'button',
            {
              class: 'pager-btn',
              disabled: props.page >= totalPages,
              onClick: () => emit('change', props.page + 1),
            },
            t('dataOps.common.nextPage')
          ),
          h(
            'button',
            {
              class: 'pager-btn',
              disabled: props.page >= totalPages,
              onClick: () => emit('change', totalPages),
            },
            t('dataOps.common.lastPage')
          ),
        ]),
      ])
    }
  },
}
