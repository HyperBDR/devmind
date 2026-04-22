<template>
  <div class="space-y-5">
    <section
      class="relative overflow-hidden rounded-2xl border border-emerald-100 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.14),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] shadow-[0_20px_50px_-38px_rgba(15,23,42,0.55)]"
    >
      <div
        class="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="flex flex-wrap items-center gap-4">
          <span
            class="inline-flex items-center rounded-full bg-slate-900 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.28em] text-white"
          >
            OnePro
          </span>
          <p class="text-sm text-gray-500">{{ scopeHint }}</p>
        </div>
        <div
          class="flex w-full max-w-2xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-end"
        >
          <div class="min-w-0 flex-1">
            <OneProDataSourceSelect layout="inline" variant="toolbar" />
          </div>
          <slot name="toolbarActions" />
        </div>
      </div>
    </section>

    <section
      class="relative overflow-hidden rounded-[28px] border border-gray-200 bg-white shadow-[0_30px_80px_-48px_rgba(15,23,42,0.32)]"
    >
      <div
        class="absolute -left-10 top-0 h-40 w-40 rounded-full bg-emerald-100/80 blur-3xl"
      />
      <div
        class="absolute right-0 top-4 h-48 w-48 rounded-full bg-sky-100/70 blur-3xl"
      />
      <div class="relative px-6 py-7 lg:px-8 lg:py-8">
        <div>
          <p
            class="text-sm font-medium uppercase tracking-[0.24em] text-emerald-600"
          >
            {{ eyebrow }}
          </p>
          <h1
            class="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-gray-950 lg:text-4xl"
          >
            {{ title }}
          </h1>
          <p
            class="mt-3 max-w-2xl text-sm leading-7 text-gray-600 lg:text-[15px]"
          >
            {{ subtitle }}
          </p>
        </div>
      </div>

      <div
        v-if="$slots.summary"
        class="relative border-t border-gray-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.35),rgba(248,250,252,0.8))] px-6 py-5 lg:px-8"
      >
        <div
          class="grid gap-4 md:grid-cols-2 xl:[grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]"
        >
          <slot name="summary" />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import OneProDataSourceSelect from './OneProDataSourceSelect.vue'

defineProps({
  eyebrow: {
    type: String,
    required: true
  },
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    required: true
  },
  scopeHint: {
    type: String,
    required: true
  }
})
</script>
