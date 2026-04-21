<template>
  <div class="w-full">
    <!-- Calendar Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-4">
        <button
          @click="previousMonth"
          class="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <h2 class="text-lg font-semibold text-gray-900">
          {{ currentMonthLabel }}
        </h2>
        <button
          @click="nextMonth"
          class="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- Calendar Grid -->
    <div class="grid grid-cols-7 gap-2 mb-4">
      <div
        v-for="day in weekDays"
        :key="day"
        class="text-center text-sm font-medium text-gray-700 py-2"
      >
        {{ day }}
      </div>
    </div>

    <div class="grid grid-cols-7 gap-2">
      <div
        v-for="(date, index) in calendarDays"
        :key="index"
        :class="[
          'min-h-[100px] p-2 border rounded cursor-pointer transition-colors',
          date.isCurrentMonth
            ? 'bg-white border-gray-200 hover:border-primary-500 hover:bg-primary-50'
            : 'bg-gray-50 border-gray-100 text-gray-400',
          date.isToday ? 'ring-2 ring-primary-500' : '',
          selectedDate && isSameDay(date.date, selectedDate)
            ? 'bg-primary-100 border-primary-500'
            : ''
        ]"
        @click="handleDateClick(date.date)"
      >
        <div class="text-sm font-medium mb-1">
          {{ date.day }}
        </div>
        <div class="space-y-1.5 max-h-[120px] overflow-y-auto">
          <div
            v-for="(periodData, index) in getPeriodDataForDate(date.date)"
            :key="`${periodData.period}-${periodData.lang || 'all'}-${index}`"
            class="flex items-center gap-1.5 text-xs py-0.5"
          >
            <span
              v-if="periodData.period === 'today'"
              class="inline-flex items-center justify-center w-5 h-5 rounded bg-blue-100 text-blue-700 font-medium text-[10px] flex-shrink-0"
              :title="t('githubTrending.filter.today')"
            >
              📅
            </span>
            <span
              v-else-if="periodData.period === 'weekly'"
              class="inline-flex items-center justify-center w-5 h-5 rounded bg-green-100 text-green-700 font-medium text-[10px] flex-shrink-0"
              :title="t('githubTrending.filter.weekly')"
            >
              📆
            </span>
            <span
              v-else-if="periodData.period === 'monthly'"
              class="inline-flex items-center justify-center w-5 h-5 rounded bg-purple-100 text-purple-700 font-medium text-[10px] flex-shrink-0"
              :title="t('githubTrending.filter.monthly')"
            >
              📊
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 text-xs flex-wrap">
                <span class="font-semibold text-gray-700">
                  {{ getPeriodLabel(periodData.period) }}
                </span>
                <span class="text-gray-400">·</span>
                <span class="font-bold text-gray-900">{{
                  periodData.count
                }}</span>
                <span class="text-gray-500 text-[10px]">{{
                  t('githubTrending.dateDetail.projects')
                }}</span>
                <span v-if="periodData.lang" class="text-gray-400">·</span>
                <span
                  v-if="periodData.lang"
                  class="text-gray-600 truncate font-medium max-w-[60px]"
                  >{{ periodData.lang }}</span
                >
              </div>
            </div>
          </div>
          <div
            v-if="
              getPeriodDataForDate(date.date).length === 0 &&
              date.isCurrentMonth
            "
            class="text-xs text-gray-400"
          >
            {{ t('githubTrending.calendar.noData') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  records: {
    type: Array,
    default: () => []
  },
  selectedDate: {
    type: Date,
    default: null
  }
})

const emit = defineEmits(['date-click', 'month-change'])

const { t, locale } = useI18n()

const currentMonth = ref(new Date())

const weekDays = computed(() => {
  if (locale.value === 'zh-CN') {
    return ['日', '一', '二', '三', '四', '五', '六']
  }
  return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
})

const currentMonthLabel = computed(() => {
  const year = currentMonth.value.getFullYear()
  const month = currentMonth.value.getMonth() + 1
  if (locale.value === 'zh-CN') {
    return `${year}年${month}月`
  }
  const monthNames = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December'
  ]
  return `${monthNames[month - 1]} ${year}`
})

const calendarDays = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = []

  const year = currentMonth.value.getFullYear()
  const month = currentMonth.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const startDate = new Date(firstDay)
  startDate.setDate(startDate.getDate() - startDate.getDay())

  for (let i = 0; i < 42; i++) {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() + i)
    const dateCopy = new Date(date)
    dateCopy.setHours(0, 0, 0, 0)

    days.push({
      date: dateCopy,
      day: date.getDate(),
      isCurrentMonth: date.getMonth() === month,
      isToday: dateCopy.getTime() === today.getTime()
    })
  }

  return days
})

const formatDateForComparison = (date) => {
  if (!date) return ''
  // If date is already a string in YYYY-MM-DD format, return it directly
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return date
  }
  // If date is a Date object, format it
  const d = date instanceof Date ? date : new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const getRecordsForDate = (date) => {
  if (!date || !props.records || props.records.length === 0) return []
  const dateStr = formatDateForComparison(date)
  return props.records.filter((record) => {
    if (!record.trending_date) return false
    // Parse date string directly to avoid timezone issues
    // API returns date as "YYYY-MM-DD" string, use it directly
    const recordDate = formatDateForComparison(record.trending_date)
    return recordDate === dateStr
  })
}

const getPeriodDataForDate = (date) => {
  const records = getRecordsForDate(date)
  if (records.length === 0) return []

  // Group by period and language
  const periodLangMap = new Map()
  records.forEach((record) => {
    const period = record.trending_period || 'unknown'
    const lang =
      record.trending_lang && record.trending_lang !== 'any'
        ? record.trending_lang
        : null
    const key = `${period}_${lang || 'all'}`

    if (!periodLangMap.has(key)) {
      periodLangMap.set(key, {
        period: period,
        count: 0,
        lang: lang
      })
    }
    const data = periodLangMap.get(key)
    data.count++
  })

  return Array.from(periodLangMap.values())
    .map((data) => ({
      period: data.period,
      count: data.count,
      lang: data.lang
    }))
    .sort((a, b) => {
      const periodOrder = { today: 1, weekly: 2, monthly: 3 }
      const orderA = periodOrder[a.period] || 99
      const orderB = periodOrder[b.period] || 99
      if (orderA !== orderB) {
        return orderA - orderB
      }
      // If same period, sort by language (null last)
      if (!a.lang && b.lang) return 1
      if (a.lang && !b.lang) return -1
      if (a.lang && b.lang) return a.lang.localeCompare(b.lang)
      return 0
    })
}

const getPeriodLabel = (period) => {
  if (period === 'today') {
    return t('githubTrending.filter.today')
  } else if (period === 'weekly') {
    return t('githubTrending.filter.weekly')
  } else if (period === 'monthly') {
    return t('githubTrending.filter.monthly')
  }
  return period
}

const isSameDay = (date1, date2) => {
  if (!date1 || !date2) return false
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  )
}

const previousMonth = () => {
  const newDate = new Date(currentMonth.value)
  newDate.setMonth(newDate.getMonth() - 1)
  currentMonth.value = newDate
  emit('month-change', newDate)
}

const nextMonth = () => {
  const newDate = new Date(currentMonth.value)
  newDate.setMonth(newDate.getMonth() + 1)
  currentMonth.value = newDate
  emit('month-change', newDate)
}

const handleDateClick = (date) => {
  const records = getRecordsForDate(date)
  if (records.length > 0) {
    emit('date-click', date)
  }
}

watch(
  () => props.selectedDate,
  (newDate) => {
    if (newDate) {
      const year = newDate.getFullYear()
      const month = newDate.getMonth()
      const currentYear = currentMonth.value.getFullYear()
      const currentMonthIndex = currentMonth.value.getMonth()

      if (year !== currentYear || month !== currentMonthIndex) {
        currentMonth.value = new Date(year, month, 1)
      }
    }
  }
)
</script>
