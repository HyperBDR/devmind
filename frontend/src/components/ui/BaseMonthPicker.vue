<template>
  <div class="relative">
    <select
      :value="internalValue"
      @change="handleChange"
      :class="selectClasses"
      :disabled="disabled"
    >
      <option value="">{{ placeholder }}</option>
      <option
        v-for="month in monthOptions"
        :key="month.value"
        :value="month.value"
      >
        {{ month.label }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, addMonths, startOfMonth } from 'date-fns'
import { zhCN, enUS } from 'date-fns/locale'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  monthsBack: {
    type: Number,
    default: 12
  },
  monthsForward: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update:modelValue'])
const { locale } = useI18n()

const dateFnsLocale = computed(() => {
  return locale.value === 'zh-CN' ? zhCN : enUS
})

const selectClasses = computed(() => {
  return 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed bg-white'
})

const internalValue = computed(() => {
  return props.modelValue || ''
})

const monthOptions = computed(() => {
  const options = []
  const now = new Date()
  const startDate = startOfMonth(addMonths(now, -props.monthsBack))
  const endDate = addMonths(now, props.monthsForward)

  let current = startDate
  while (current <= endDate) {
    const value = format(current, 'yyyy-MM')
    let label
    if (locale.value === 'zh-CN') {
      label = format(current, 'yyyy年M月', { locale: dateFnsLocale.value })
    } else {
      label = format(current, 'MMMM yyyy', { locale: dateFnsLocale.value })
    }
    options.push({ value, label })
    current = addMonths(current, 1)
  }

  return options.reverse()
})

const handleChange = (event) => {
  const value = event.target.value
  emit('update:modelValue', value)
}
</script>
