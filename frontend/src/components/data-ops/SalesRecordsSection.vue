<template>
  <section class="space-y-5">
    <Toolbar>
      <select
        :value="filters.status"
        class="field-sm"
        @change="$emit('update-filter', 'status', $event.target.value)"
      >
        <option value="">{{ t('dataOps.filters.allStatuses') }}</option>
        <option value="active">active</option>
        <option value="expired">expired</option>
        <option value="pending">pending</option>
      </select>
      <input
        :value="filters.region"
        class="field-sm"
        :placeholder="t('dataOps.filters.region')"
        @input="$emit('update-filter', 'region', $event.target.value)"
      />
      <input
        :value="filters.product_type"
        class="field-sm"
        :placeholder="t('dataOps.filters.productType')"
        @input="$emit('update-filter', 'product_type', $event.target.value)"
      />
      <button class="btn-secondary" type="button" @click="$emit('load')">
        {{ t('dataOps.common.query') }}
      </button>
      <button
        v-if="canExport"
        class="btn-secondary"
        type="button"
        @click="$emit('download')"
      >
        {{ t('dataOps.common.export') }}
      </button>
    </Toolbar>
    <DataTable
      :columns="columns"
      :rows="records"
      :empty-text="t('dataOps.empty.sales')"
    />
    <Pager
      :page="page"
      :page-size="pageSize"
      :total="total"
      @change="$emit('page-change', $event)"
    />
  </section>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { DataTable, Pager, Toolbar } from './DataOpsPrimitives'

const { t } = useI18n()

defineProps({
  canExport: { type: Boolean, default: false },
  columns: { type: Array, required: true },
  filters: { type: Object, required: true },
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  records: { type: Array, default: () => [] },
  total: { type: Number, required: true },
})

defineEmits(['download', 'load', 'page-change', 'update-filter'])
</script>
