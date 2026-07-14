<template>
  <section class="space-y-5">
    <Toolbar>
      <input
        :value="filters.customer_name"
        class="field-sm"
        :placeholder="t('dataOps.filters.customer')"
        @input="$emit('update-filter', 'customer_name', $event.target.value)"
        @keyup.enter="$emit('load')"
      />
      <select
        :value="filters.signing_entity"
        class="field-sm"
        @change="$emit('update-filter', 'signing_entity', $event.target.value)"
      >
        <option value="">{{ t('dataOps.filters.allEntities') }}</option>
        <option
          v-for="entity in filterOptions.signing_entity || []"
          :key="entity"
          :value="entity"
        >
          {{ entity }}
        </option>
      </select>
      <select
        :value="filters.sales_person"
        class="field-sm"
        @change="$emit('update-filter', 'sales_person', $event.target.value)"
      >
        <option value="">{{ t('dataOps.filters.allOwners') }}</option>
        <option
          v-for="name in filterOptions.sales_person || []"
          :key="name"
          :value="name"
        >
          {{ name }}
        </option>
      </select>
      <select
        :value="filters.status"
        class="field-sm"
        @change="$emit('update-filter', 'status', $event.target.value)"
      >
        <option value="">{{ t('dataOps.filters.allStatuses') }}</option>
        <option
          v-for="status in filterOptions.status || []"
          :key="status"
          :value="status"
        >
          {{ status }}
        </option>
      </select>
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
      :rows="contracts"
      :empty-text="t('dataOps.empty.contracts')"
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
  contracts: { type: Array, default: () => [] },
  filterOptions: { type: Object, default: () => ({}) },
  filters: { type: Object, required: true },
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
})

defineEmits(['download', 'load', 'page-change', 'update-filter'])
</script>
