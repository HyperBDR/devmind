<template>
  <header class="llm-ops-header px-5 py-3 lg:px-7">
    <div class="page-hero">
      <div class="page-hero-copy">
        <div class="space-y-3 lg:hidden">
          <section v-for="group in navGroups" :key="group.key">
            <p
              class="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400"
            >
              {{ group.label }}
            </p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="item in group.items"
                :key="item.key"
                type="button"
                class="llm-mobile-nav-item px-3 py-2 text-xs font-semibold"
                :class="{ 'is-active': activeSection === item.key }"
                @click="$emit('update:activeSection', item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </section>
        </div>
        <p
          class="page-hero-eyebrow mt-4 text-xs font-semibold uppercase tracking-[0.18em] text-agione-600 lg:mt-0"
        >
          {{ activeNav.eyebrow }}
        </p>
        <h2 class="page-hero-title mt-1 text-2xl font-semibold text-slate-900">
          {{ activeNav.label }}
        </h2>
        <p
          class="page-hero-description mt-1.5 max-w-3xl text-sm leading-6 text-slate-500"
        >
          {{ activeNav.description }}
        </p>
      </div>
      <div v-if="showHeroActions" class="page-hero-actions">
        <div v-if="showGlobalToolbar" class="page-hero-group">
          <div class="currency-control page-toolbar-control">
            <span>{{ t('llmOps.toolbar.displayCurrency') }}</span>
            <CompactSelect
              v-model="displayCurrencyModel"
              :options="displayCurrencyOptions"
              class-name="w-28"
              size="sm"
            />
          </div>
          <span v-if="exchangeRateLabel" class="page-toolbar-chip">
            {{ exchangeRateLabel }}
          </span>
          <button
            type="button"
            class="btn-secondary page-toolbar-button refresh-action-button btn-action-refresh"
            :disabled="loading"
            @click="$emit('refresh')"
          >
            <svg
              aria-hidden="true"
              :class="['refresh-action-icon', { 'is-spinning': loading }]"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              viewBox="0 0 24 24"
            >
              <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
              <path d="M3 16v5h5" />
              <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
              <path d="M21 3v5h-5" />
            </svg>
            {{ t('common.refresh') }}
          </button>
        </div>
        <div v-if="showPlatformControl" class="page-hero-group">
          <div class="currency-control page-toolbar-control">
            <span>{{ t('llmOps.toolbar.resalePlatform') }}</span>
            <CompactSelect
              v-model="selectedResalePlatformIdModel"
              :options="resalePlatformOptions"
              class-name="w-56"
              :menu-min-width="260"
              size="sm"
            />
          </div>
          <div v-if="showPlatformActions" class="page-toolbar-button-group">
            <button
              type="button"
              class="btn-secondary page-toolbar-button btn-action-config"
              @click="$emit('open-platform', agionePlatform)"
            >
              {{ t('llmOps.toolbar.platformConfig') }}
            </button>
            <button
              type="button"
              class="btn-primary page-toolbar-button btn-action-create"
              @click="$emit('open-platform', null)"
            >
              {{ t('llmOps.toolbar.createPlatform') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  activeNav: {
    type: Object,
    required: true
  },
  activeSection: {
    type: String,
    required: true
  },
  agionePlatform: {
    type: Object,
    default: null
  },
  displayCurrency: {
    type: String,
    required: true
  },
  exchangeRateLabel: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    required: true
  },
  navGroups: {
    type: Array,
    required: true
  },
  resalePlatformOptions: {
    type: Array,
    required: true
  },
  selectedResalePlatformId: {
    type: [String, Number],
    default: ''
  }
})

const emit = defineEmits([
  'open-platform',
  'refresh',
  'update:activeSection',
  'update:displayCurrency',
  'update:selectedResalePlatformId'
])

const { t } = useI18n()

const displayCurrencyOptions = computed(() => [
  { label: t('llmOps.currency.cny'), value: 'CNY' },
  { label: t('llmOps.currency.usd'), value: 'USD' }
])

const displayCurrencyModel = computed({
  get: () => props.displayCurrency,
  set: (value) => emit('update:displayCurrency', value)
})

const selectedResalePlatformIdModel = computed({
  get: () => props.selectedResalePlatformId,
  set: (value) => emit('update:selectedResalePlatformId', value)
})

const showPlatformControl = computed(() =>
  ['monitor', 'reseller'].includes(props.activeSection)
)
const showPlatformActions = computed(() => props.activeSection === 'reseller')
const showGlobalToolbar = computed(() => props.activeSection !== 'workflow')
const showHeroActions = computed(
  () => showGlobalToolbar.value || showPlatformControl.value
)
</script>
