import { h } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatAmount } from '@/composables/useDataOpsConsole'

export const Panel = {
  props: {
    title: { type: String, required: true }
  },
  setup(props, { slots }) {
    return () =>
      h('section', { class: 'rounded-xl border border-slate-200 bg-white' }, [
        h(
          'div',
          { class: 'border-b border-slate-200 px-4 py-3' },
          h('h3', { class: 'text-sm font-bold text-slate-950' }, props.title)
        ),
        h('div', { class: 'p-4' }, slots.default?.())
      ])
  }
}

export const Toolbar = {
  setup(_, { slots }) {
    return () =>
      h(
        'div',
        {
          class:
            'flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4'
        },
        slots.default?.()
      )
  }
}

export const Kpi = {
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], required: true }
  },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-xl border border-slate-200 bg-white p-4' }, [
        h('p', { class: 'text-xs font-medium text-slate-500' }, props.label),
        h(
          'p',
          { class: 'mt-2 text-2xl font-bold text-slate-950' },
          String(props.value)
        )
      ])
  }
}

export const DataRow = {
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], required: true }
  },
  setup(props) {
    return () =>
      h('div', { class: 'flex items-start justify-between gap-3 text-sm' }, [
        h('span', { class: 'text-slate-500' }, props.label),
        h('strong', { class: 'text-right text-slate-900' }, String(props.value))
      ])
  }
}

export const EmptyState = {
  props: {
    text: { type: String, default: '' }
  },
  setup(props) {
    const { t } = useI18n()
    return () =>
      h(
        'div',
        {
          class:
            'rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400'
        },
        props.text || t('dataOps.common.noData')
      )
  }
}

export const MiniList = {
  props: {
    title: { type: String, required: true },
    items: { type: Array, default: () => [] },
    labelKey: { type: String, required: true },
    valueKey: { type: String, required: true }
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
                      locale: locale.value
                    })
                  )
                ])
              )
            )
          : h(EmptyState)
      ])
  }
}

export const DataTable = {
  props: {
    columns: { type: Array, required: true },
    rows: { type: Array, default: () => [] },
    emptyText: { type: String, default: '' }
  },
  setup(props) {
    const { t } = useI18n()
    const valueFor = (row, col) => {
      const value = row[col.key]
      if (col.format) return col.format(value, row)
      return value === null || value === undefined || value === '' ? '-' : value
    }
    return () =>
      h(
        'div',
        {
          class: 'overflow-hidden rounded-xl border border-slate-200 bg-white'
        },
        [
          h(
            'div',
            { class: 'divide-y divide-slate-100 md:hidden' },
            props.rows.length
              ? props.rows.map((row, rowIndex) =>
                  h(
                    'article',
                    {
                      key: row.id || row.uuid || rowIndex,
                      class: 'space-y-3 p-4'
                    },
                    [
                      h(
                        'h3',
                        { class: 'text-sm font-bold text-slate-900' },
                        String(valueFor(row, props.columns[0]))
                      ),
                      h(
                        'dl',
                        {
                          class: 'grid grid-cols-1 gap-2 text-xs sm:grid-cols-2'
                        },
                        props.columns.slice(1).map((col) =>
                          h(
                            'div',
                            {
                              key: col.key,
                              class:
                                'flex items-start justify-between gap-3 sm:block'
                            },
                            [
                              h('dt', { class: 'text-slate-500' }, col.label),
                              h(
                                'dd',
                                {
                                  class:
                                    'break-words text-right font-medium text-slate-800 sm:mt-1 sm:text-left'
                                },
                                valueFor(row, col)
                              )
                            ]
                          )
                        )
                      )
                    ]
                  )
                )
              : h(
                  'p',
                  { class: 'px-4 py-10 text-center text-slate-400' },
                  props.emptyText || t('dataOps.common.noData')
                )
          ),
          h('div', { class: 'hidden max-h-[65vh] overflow-auto md:block' }, [
            h(
              'table',
              { class: 'min-w-full divide-y divide-slate-200 text-xs' },
              [
                h(
                  'thead',
                  {
                    class:
                      'bg-slate-50 text-left font-semibold uppercase text-slate-500'
                  },
                  h(
                    'tr',
                    props.columns.map((col, index) =>
                      h(
                        'th',
                        {
                          key: col.key,
                          class: [
                            'sticky top-0 z-10 whitespace-nowrap bg-slate-50 px-4 py-3',
                            index === 0 ? 'left-0 z-20' : ''
                          ]
                        },
                        col.label
                      )
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
                          {
                            key: row.id || row.uuid || JSON.stringify(row),
                            class: 'group hover:bg-indigo-50/20'
                          },
                          props.columns.map((col, index) =>
                            h(
                              'td',
                              {
                                key: col.key,
                                class: [
                                  'max-w-[18rem] truncate px-4 py-3 text-slate-700',
                                  index === 0
                                    ? 'sticky left-0 bg-white font-medium group-hover:bg-indigo-50'
                                    : ''
                                ]
                              },
                              valueFor(row, col)
                            )
                          )
                        )
                      )
                    : h('tr', [
                        h(
                          'td',
                          {
                            class: 'px-4 py-10 text-center text-slate-400',
                            colspan: props.columns.length
                          },
                          props.emptyText || t('dataOps.common.noData')
                        )
                      ])
                )
              ]
            )
          ])
        ]
      )
  }
}

export const Pager = {
  props: {
    page: { type: Number, required: true },
    total: { type: Number, required: true },
    pageSize: { type: Number, required: true }
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n()
    return () => {
      const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize))
      return h(
        'div',
        {
          class:
            'flex flex-col gap-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between'
        },
        [
          h(
            'span',
            t('dataOps.common.totalPages', {
              total: props.total,
              pages: totalPages
            })
          ),
          h(
            'div',
            {
              class:
                'flex items-center justify-between gap-1 sm:justify-end sm:gap-2'
            },
            [
              h(
                'button',
                {
                  class:
                    'pager-btn hidden min-h-11 sm:inline-flex sm:items-center',
                  disabled: props.page <= 1,
                  onClick: () => emit('change', 1)
                },
                t('dataOps.common.firstPage')
              ),
              h(
                'button',
                {
                  class: 'pager-btn inline-flex min-h-11 items-center',
                  disabled: props.page <= 1,
                  onClick: () => emit('change', props.page - 1)
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
                  class: 'pager-btn inline-flex min-h-11 items-center',
                  disabled: props.page >= totalPages,
                  onClick: () => emit('change', props.page + 1)
                },
                t('dataOps.common.nextPage')
              ),
              h(
                'button',
                {
                  class:
                    'pager-btn hidden min-h-11 sm:inline-flex sm:items-center',
                  disabled: props.page >= totalPages,
                  onClick: () => emit('change', totalPages)
                },
                t('dataOps.common.lastPage')
              )
            ]
          )
        ]
      )
    }
  }
}
