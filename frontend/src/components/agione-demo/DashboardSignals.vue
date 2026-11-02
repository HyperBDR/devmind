<template>
  <section class="panel event-column" data-panel="events">
    <div class="event-heading">
      <div class="event-title-group">
        <h2>待核实线索</h2>
        <small>已有快照 · 只读诊断</small>
      </div>
    </div>
    <div v-if="data?.comparison" class="event-rule-warning" role="status">
      <b>{{ data.comparison.state || '已缓存比较' }}</b>
      <p>
        {{
          data.comparison.reason || '比较仅使用已存在的前期快照，不触发补采。'
        }}
      </p>
    </div>
    <div class="event-tabs" role="group" aria-label="客户线索">
      <button
        v-for="tab in tabs"
        :key="tab[0]"
        :aria-pressed="kind === tab[0]"
        @click="kind = tab[0]"
      >
        {{ tab[1] }}
      </button>
    </div>
    <div class="event-list">
      <article
        v-for="row in rows"
        :key="row.customerTenantId"
        class="event-item"
      >
        <div class="event-item-head">
          <button class="link" @click="$emit('customer', row.customerTenantId)">
            {{ row.name || row.customerTenantId }}</button
          ><span>{{ fmt(row.summary?.requestCount) }} 次请求</span>
        </div>
        <p>
          {{
            (Array.isArray(row.signals)
              ? row.signals
              : row.signals?.signals || []
            )
              .map((x) => names[x] || x)
              .join(' · ') ||
            row.reason ||
            '使用事实待核实'
          }}
        </p>
        <p>
          成功率 {{ percent(row.summary?.successRate) }} · 失败
          {{ fmt(row.summary?.failureCount) }}
        </p>
        <div class="button-line">
          <button class="link" @click="$emit('customer', row.customerTenantId)">
            查看客户画像 →</button
          ><button
            class="link"
            @click="$emit('requests', row.customerTenantId)"
          >
            查看请求证据 →
          </button>
        </div>
      </article>
      <div v-if="!rows.length" class="empty">
        当前快照没有该类客户线索；缺失比较不会被补成零。
      </div>
    </div>
    <div class="event-bottom">
      <p>诊断只提示待核实事实；记录跟进、采集和导出未开放写操作。</p>
    </div>
  </section>
</template>
<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ data: { type: Object, default: null } })
defineEmits(['customer', 'requests'])
const kind = ref('all')
const tabs = [
  ['all', '全部'],
  ['inactive', '近期无调用'],
  ['blocked', '接入受阻'],
  ['decline', '使用下降'],
  ['technical', '技术失败']
]
const names = {
  inactive: '近期无调用',
  blocked: '接入受阻',
  decline: '使用下降',
  technical: '技术失败偏高',
  growth: '增长机会',
  trial: '少量探索',
  stable: '稳定用量'
}
const rows = computed(() => {
  const raw = props.data?.worklist || props.data?.customers || []
  const all = Array.isArray(raw) ? raw : raw.items || []
  return kind.value === 'all'
    ? all
    : all.filter((x) =>
        (Array.isArray(x.signals)
          ? x.signals
          : x.signals?.signals || []
        ).includes(kind.value)
      )
})
const fmt = (x) =>
  typeof x === 'number' ? new Intl.NumberFormat('zh-CN').format(x) : '—'
const percent = (x) =>
  typeof x === 'number'
    ? `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(x)}%`
    : '—'
</script>
