<template>
  <VueDatePicker
    :model-value="modelValue || null"
    model-type="yyyy-MM-dd"
    :time-config="timeConfig"
    :formats="datepickerFormats"
    :teleport="true"
    :auto-apply="true"
    :clearable="clearable"
    :disabled="disabled"
    :placeholder="resolvedPlaceholder"
    :locale="pickerLocale"
    :ui="datepickerUi"
    class="w-full text-xs"
    @update:model-value="onUpdate"
  />
</template>

<script setup>
import { computed } from 'vue'
import { enUS, zhCN } from 'date-fns/locale'
import { useI18n } from 'vue-i18n'
import { VueDatePicker } from '@vuepic/vue-datepicker'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  clearable: {
    type: Boolean,
    default: true,
  },
  inputClass: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue'])
const { locale } = useI18n()

const timeConfig = {
  enableTimePicker: false,
}

const normalizedLanguage = computed(() => {
  const lang = locale.value || 'en'
  return lang.startsWith('zh') ? 'zh-CN' : 'en'
})

const pickerLocale = computed(() =>
  normalizedLanguage.value === 'zh-CN' ? zhCN : enUS,
)

const resolvedFormat = computed(() =>
  normalizedLanguage.value === 'zh-CN' ? 'yyyy/MM/dd' : 'MM/dd/yyyy',
)

const datepickerFormats = computed(() => ({
  input: resolvedFormat.value,
  preview: resolvedFormat.value,
}))

const resolvedPlaceholder = computed(() => {
  if (props.placeholder) {
    return props.placeholder
  }
  return normalizedLanguage.value === 'zh-CN' ? '年 / 月 / 日' : 'MM / DD / YYYY'
})

const defaultInputClass =
  'h-10 w-full min-w-0 rounded-lg border border-dm-border bg-white px-3 py-2 text-xs text-dm-text focus:outline-hidden focus:border-blue-500'

const datepickerUi = computed(() => ({
  input: props.inputClass || defaultInputClass,
}))

function onUpdate(value) {
  emit('update:modelValue', value || '')
}
</script>
