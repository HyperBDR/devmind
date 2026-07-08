<template>
  <section class="space-y-5">
    <Toolbar>
      <input
        :value="filters.customer_name"
        class="field-sm"
        placeholder="客户名称"
        @input="$emit('update-filter', 'customer_name', $event.target.value)"
        @keyup.enter="$emit('load')"
      />
      <select
        :value="filters.sales_person"
        class="field-sm"
        @change="$emit('update-filter', 'sales_person', $event.target.value)"
      >
        <option value="">全部负责人</option>
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
        <option value="">全部状态</option>
        <option
          v-for="status in filterOptions.status || []"
          :key="status"
          :value="status"
        >
          {{ status }}
        </option>
      </select>
      <button class="btn-secondary" type="button" @click="$emit('load')">
        查询
      </button>
      <button
        v-if="canExport"
        class="btn-secondary"
        type="button"
        @click="$emit('download')"
      >
        导出
      </button>
    </Toolbar>
    <DataTable :columns="columns" :rows="contracts" empty-text="暂无合同记录" />
    <Pager
      :page="page"
      :page-size="pageSize"
      :total="total"
      @change="$emit('page-change', $event)"
    />
  </section>
</template>

<script setup>
import { DataTable, Pager, Toolbar } from './DataOpsPrimitives'

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
