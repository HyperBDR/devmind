<template>
  <section class="space-y-5">
    <Toolbar>
      <select
        :value="filters.status"
        class="field-sm"
        @change="$emit('update-filter', 'status', $event.target.value)"
      >
        <option value="">全部状态</option>
        <option value="active">active</option>
        <option value="expired">expired</option>
        <option value="pending">pending</option>
      </select>
      <input
        :value="filters.region"
        class="field-sm"
        placeholder="地区"
        @input="$emit('update-filter', 'region', $event.target.value)"
      />
      <input
        :value="filters.product_type"
        class="field-sm"
        placeholder="产品类型"
        @input="$emit('update-filter', 'product_type', $event.target.value)"
      />
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
    <DataTable
      :columns="columns"
      :rows="records"
      empty-text="暂无海外销售记录"
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
import { DataTable, Pager, Toolbar } from './DataOpsPrimitives'

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
