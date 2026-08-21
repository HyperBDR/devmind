<template>
  <header class="llm-ops-header px-5 py-3 lg:px-7">
    <div class="page-hero">
      <div class="page-hero-copy">
        <button
          ref="mobileNavigationTrigger"
          type="button"
          class="llm-mobile-navigation-trigger lg:hidden"
          :aria-expanded="mobileNavigationOpen"
          aria-controls="llm-ops-mobile-navigation"
          :aria-label="t('llmOps.toolbar.openNavigation')"
          @click="$emit('open-navigation')"
        >
          <svg
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <span>{{ t('llmOps.toolbar.navigation') }}</span>
        </button>
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
        <div v-if="toolbar.currency || toolbar.refresh" class="page-hero-group">
          <div
            v-if="toolbar.currency"
            class="currency-control page-toolbar-control"
          >
            <span>{{ t('llmOps.toolbar.displayCurrency') }}</span>
            <CompactSelect
              v-model="displayCurrencyModel"
              :options="displayCurrencyOptions"
              class-name="w-28"
              :disabled="actionsDisabled"
              size="sm"
            />
          </div>
          <span
            v-if="toolbar.currency && exchangeRateLabel"
            class="page-toolbar-chip"
          >
            {{ exchangeRateLabel }}
          </span>
          <button
            v-if="toolbar.refresh"
            type="button"
            class="btn-secondary page-toolbar-button refresh-action-button btn-action-refresh"
            :disabled="loading || actionsDisabled"
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
              :disabled="actionsDisabled"
              :menu-min-width="260"
              size="sm"
            />
          </div>
          <div v-if="showPlatformActions" class="page-toolbar-button-group">
            <button
              type="button"
              class="btn-secondary page-toolbar-button btn-action-config"
              :disabled="actionsDisabled"
              @click="$emit('open-platform', agionePlatform)"
            >
              {{ t('llmOps.toolbar.platformConfig') }}
            </button>
            <button
              type="button"
              class="btn-primary page-toolbar-button btn-action-create"
              :disabled="actionsDisabled"
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
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { toolbarForSection } from '@/utils/llmOpsSectionData'

const props = defineProps({
  activeNav: {
    type: Object,
    required: true
  },
  activeSection: {
    type: String,
    required: true
  },
  actionsDisabled: {
    type: Boolean,
    default: false
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
  mobileNavigationOpen: {
    type: Boolean,
    default: false
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
  'open-navigation',
  'open-platform',
  'refresh',
  'update:activeSection',
  'update:displayCurrency',
  'update:selectedResalePlatformId'
])

const { t } = useI18n()
const mobileNavigationTrigger = ref(null)

watch(
  () => props.mobileNavigationOpen,
  (isOpen, wasOpen) => {
    if (isOpen || !wasOpen) return
    nextTick(() => {
      const trigger = mobileNavigationTrigger.value
      if (trigger?.offsetParent !== null) trigger?.focus()
    })
  }
)

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
  [
    'channelMatrix',
    'listingRisk',
    'modelWorkbench',
    'monitor',
    'priceChanges',
    'reseller'
  ].includes(props.activeSection)
)
const showPlatformActions = computed(() => props.activeSection === 'reseller')
const toolbar = computed(() => toolbarForSection(props.activeSection))
const showHeroActions = computed(
  () =>
    toolbar.value.currency || toolbar.value.refresh || showPlatformControl.value
)
</script>
