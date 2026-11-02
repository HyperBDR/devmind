<template>
  <section
    class="profile-finance-card"
    data-panel="finance"
    aria-label="客户账户与消耗"
  >
    <div class="finance-card-grid">
      <section class="finance-balance">
        <div class="finance-field-head">
          <h3>账户余额</h3>
          <span class="finance-state" role="status">{{
            available ? '已授权缓存 · 非实时' : '暂不可用'
          }}</span>
        </div>
        <div class="finance-amount">
          <template v-if="balances.length"
            ><strong v-for="(row, index) in balances" :key="index"
              >{{ money(row.value) }} {{ row.unit || '单位未标明' }}</strong
            ></template
          ><strong v-else>—</strong>
        </div>
        <div class="finance-field-footer">
          原采集时间
          {{
            time(
              finance.latestReadAt || finance.summarySections?.accounts?.readAt
            )
          }}
        </div>
      </section>
      <section class="finance-cycle">
        <div class="finance-field-head">
          <h3>账期消耗</h3>
          <span class="finance-period">平台账期快照</span>
        </div>
        <div class="finance-amount">
          <template v-if="cycles.length"
            ><strong v-for="(row, index) in cycles" :key="index"
              >{{ money(row.value) }} {{ row.unit || '单位未标明'
              }}<small>{{ row.period }}</small></strong
            ></template
          ><strong v-else>—</strong>
        </div>
        <div class="finance-field-footer">
          原采集时间
          {{
            time(
              finance.latestReadAt || finance.summarySections?.overview?.readAt
            )
          }}
        </div>
      </section>
    </div>
    <p class="finance-reading-note">
      {{
        available
          ? '余额为最近已采集值，非实时；客户财务不随调用日期变化。'
          : value?.reason || '当前客户没有可用的已授权财务缓存，不触发补采。'
      }}
    </p>
  </section>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ value: { type: Object, default: null } })
const finance = computed(
  () => props.value?.finance || props.value?.data || props.value || {}
)
const available = computed(
  () =>
    props.value?.available !== false &&
    (!!finance.value.balances ||
      !!finance.value.accounts ||
      !!finance.value.overview ||
      !!finance.value.cycles)
)
const balances = computed(
  () =>
    finance.value.balances ||
    (finance.value.accounts || []).map((x) => ({
      value: x.balance ?? x.availableBalance,
      unit: x.currency || x.currencyCode
    }))
)
const cycles = computed(
  () =>
    finance.value.cycles ||
    (finance.value.overview?.cycleConsumedCredit != null
      ? [
          {
            value: finance.value.overview.cycleConsumedCredit,
            unit:
              finance.value.accounts?.[0]?.currency ||
              finance.value.accounts?.[0]?.currencyCode,
            period: finance.value.overview.currentCycle
          }
        ]
      : [])
)
const money = (x) =>
  x != null && String(x).trim() !== '' && Number.isFinite(Number(x))
    ? new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(Number(x))
    : '—'
const time = (x) =>
  x && Number.isFinite(Date.parse(x))
    ? new Date(x).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
    : '未提供'
</script>
