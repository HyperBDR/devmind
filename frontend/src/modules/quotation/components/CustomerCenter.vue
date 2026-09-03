<script setup lang="ts">
import { computed, ref } from 'vue'
import { Mail, Phone, Plus, RefreshCw, Search, X } from 'lucide-vue-next'
import type { Quotation } from '../types'
import { useQuotationI18n } from '../composables/useQuotationI18n'

type CustomerContact = {
  name: string
  email: string
  phone: string
  quoteCount: number
}

type Customer = {
  company: string
  contacts: CustomerContact[]
  quoteCount: number
  updatedAt: string
}

const props = defineProps<{
  quotations: Quotation[]
}>()

const { t } = useQuotationI18n()

const emit = defineEmits<{
  navigateToCreate: [customer?: CustomerContact & { company: string }]
  toast: [message: string, type?: 'success' | 'info' | 'error']
  refresh: []
}>()

const search = ref('')
const selectedCustomer = ref<Customer | null>(null)
const showContactForm = ref(false)
const showCustomerDetails = ref(false)
const customerForQuote = ref<Customer | null>(null)
const contactName = ref('')
const contactEmail = ref('')
const contactPhone = ref('')
const contactRole = ref('')
const refreshing = ref(false)
const lastSyncedAt = ref<Date | null>(null)

const customers = computed<Customer[]>(() => {
  const grouped = new Map<string, Customer>()
  props.quotations.forEach((quote) => {
    const company = quote.clientCompany?.trim()
    if (!company) return
    const key = company.toLowerCase()
    const customer = grouped.get(key) || {
      company,
      contacts: [],
      quoteCount: 0,
      updatedAt: quote.createdAt || quote.quoteDate || '-',
    }
    customer.quoteCount += 1
    const contactKey = `${quote.contactPerson}|${quote.email}`.toLowerCase()
    if (quote.contactPerson || quote.email) {
      const existing = customer.contacts.find(
        (contact) => `${contact.name}|${contact.email}`.toLowerCase() === contactKey,
      )
      if (existing) existing.quoteCount += 1
      else {
        customer.contacts.push({
          name: quote.contactPerson || '未填写联系人',
          email: quote.email || '-',
          phone: '-',
          quoteCount: 1,
        })
      }
    }
    if (quote.createdAt && quote.createdAt > customer.updatedAt) {
      customer.updatedAt = quote.createdAt
    }
    grouped.set(key, customer)
  })
  return [...grouped.values()]
})

function formatLastSynced() {
  if (!lastSyncedAt.value) return t('quotation.customerCenter.notSynced')
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(lastSyncedAt.value)
}

async function refreshCustomers() {
  if (refreshing.value) return
  refreshing.value = true
  emit('refresh')
  await new Promise((resolve) => window.setTimeout(resolve, 300))
  lastSyncedAt.value = new Date()
  refreshing.value = false
}

const filteredCustomers = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return customers.value
  return customers.value.filter((customer) =>
    [customer.company, ...customer.contacts.flatMap((contact) => [contact.name, contact.email])]
      .join(' ')
      .toLowerCase()
      .includes(keyword),
  )
})

function openContacts(customer: Customer) {
  selectedCustomer.value = customer
  showCustomerDetails.value = false
}

function openDetails(customer: Customer) {
  selectedCustomer.value = customer
  showCustomerDetails.value = true
}

function closePanels() {
  selectedCustomer.value = null
  showContactForm.value = false
  showCustomerDetails.value = false
  customerForQuote.value = null
}

function requestQuote(customer: Customer) {
  if (customer.contacts.length > 1) {
    customerForQuote.value = customer
    return
  }
  const contact = customer.contacts[0]
  if (contact) {
    emit('navigateToCreate', { company: customer.company, ...contact })
  } else {
    emit('navigateToCreate')
  }
}

function useContactForQuote(customer: Customer, contact: CustomerContact) {
  customerForQuote.value = null
  emit('navigateToCreate', { company: customer.company, ...contact })
}

function copyContact(value: string) {
  if (value === '-') return
  void navigator.clipboard?.writeText(value)
  emit('toast', '联系方式已复制', 'success')
}

function saveContact() {
  if (!contactName.value.trim() || !selectedCustomer.value) return
  emit('toast', '联系人已添加到当前页面', 'success')
  showContactForm.value = false
  contactName.value = ''
  contactEmail.value = ''
  contactPhone.value = ''
  contactRole.value = ''
}
</script>

<template>
  <section class="space-y-4">
    <div class="dm-card flex flex-wrap items-center justify-between gap-4 p-5">
      <div>
        <h2 class="text-xl font-bold text-dm-text">{{ t('quotation.customerCenter.title') }}</h2>
        <p class="mt-1 text-sm text-dm-text-tertiary">
          {{ t('quotation.customerCenter.subtitle') }}
        </p>
      </div>
      <button
        type="button"
        class="dm-btn-primary cursor-pointer px-4 py-2 text-sm"
        @click="showContactForm = true; selectedCustomer = null"
        >
        <Plus class="h-4 w-4" /> {{ t('quotation.customerCenter.addCustomer') }}
      </button>
    </div>

    <div class="dm-card flex flex-wrap items-center gap-3 p-4">
      <label class="relative min-w-[280px] flex-1">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary" />
        <input
          v-model="search"
          type="search"
          class="w-full rounded-dm border border-dm-border bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-dm-primary"
          :placeholder="t('quotation.customerCenter.searchPlaceholder')"
        />
      </label>
      <div class="flex items-center gap-3 text-sm text-dm-text-tertiary">
        <span>{{ t('quotation.customerCenter.customerCount', { count: filteredCustomers.length }) }}</span>
        <span class="hidden sm:inline">{{ t('quotation.customerCenter.lastSynced', { time: formatLastSynced() }) }}</span>
        <button
          type="button"
          class="dm-btn-default cursor-pointer px-3 py-2 text-sm"
          :disabled="refreshing"
          @click="refreshCustomers"
        >
          <RefreshCw :class="['h-4 w-4', refreshing ? 'animate-spin' : '']" />
          {{ refreshing ? t('quotation.customerCenter.refreshing') : t('quotation.customerCenter.refresh') }}
        </button>
      </div>
    </div>

    <div class="dm-card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="dm-table min-w-[760px]">
          <thead>
            <tr>
              <th>{{ t('quotation.customerCenter.columns.company') }}</th>
              <th>{{ t('quotation.customerCenter.columns.contacts') }}</th>
              <th>{{ t('quotation.customerCenter.columns.recentContact') }}</th>
              <th>{{ t('quotation.customerCenter.columns.quotes') }}</th>
              <th>{{ t('quotation.customerCenter.columns.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="customer in filteredCustomers" :key="customer.company">
              <td>
                <button
                  type="button"
                  class="cursor-pointer font-semibold text-dm-text hover:text-dm-primary"
                  @click="openDetails(customer)"
                >
                  {{ customer.company }}
                </button>
              </td>
              <td>
                <button
                  type="button"
                  class="cursor-pointer font-medium text-dm-primary hover:underline"
                  @click="openContacts(customer)"
                >
                  {{ t('quotation.customerCenter.contactCount', { count: customer.contacts.length }) }}
                </button>
              </td>
              <td>
                <div class="max-w-[260px] truncate">
                  {{ customer.contacts[0]?.name || t('quotation.customerCenter.noContact') }}
                </div>
                <div class="max-w-[260px] truncate text-xs text-dm-text-tertiary">
                  {{ customer.contacts[0]?.email || '-' }}
                </div>
              </td>
              <td>{{ customer.quoteCount }}</td>
              <td>
                <button
                  type="button"
                  class="mr-3 cursor-pointer text-dm-primary hover:underline"
                  @click="openDetails(customer)"
                >{{ t('quotation.common.view') }}</button>
                <button
                  type="button"
                  class="cursor-pointer text-dm-primary hover:underline"
                  @click="requestQuote(customer)"
                >{{ t('quotation.customerCenter.newQuote') }}</button>
              </td>
            </tr>
            <tr v-if="!filteredCustomers.length">
              <td colspan="5" class="py-12 text-center text-dm-text-tertiary">
                {{ t('quotation.customerCenter.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      v-if="selectedCustomer || showContactForm"
      class="fixed inset-0 z-40 bg-slate-950/25"
      @click="closePanels"
    />
    <aside
      v-if="selectedCustomer"
      class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[30rem] flex-col border-l border-dm-border bg-white shadow-2xl"
    >
      <div class="flex items-start justify-between border-b border-dm-border-light p-5">
        <div>
          <h3 class="text-lg font-bold text-dm-text">{{ selectedCustomer.company }}</h3>
          <p class="mt-1 text-sm text-dm-text-tertiary">
            {{ t('quotation.customerCenter.detailSubtitle', { count: selectedCustomer.contacts.length }) }}
          </p>
        </div>
        <button type="button" class="cursor-pointer text-dm-text-tertiary" aria-label="关闭" @click="closePanels"><X class="h-5 w-5" /></button>
      </div>
      <div v-if="showCustomerDetails" class="grid grid-cols-2 gap-3 border-b border-dm-border-light p-5 text-sm">
        <div class="rounded-dm bg-dm-page p-3"><p class="text-dm-text-tertiary">{{ t('quotation.customerCenter.columns.quotes') }}</p><p class="mt-1 text-lg font-semibold">{{ selectedCustomer.quoteCount }}</p></div>
      </div>
      <div class="flex items-center justify-between px-5 pb-2 pt-5">
        <h4 class="font-semibold text-dm-text">{{ t('quotation.customerCenter.columns.contacts') }}</h4>
        <button type="button" class="text-sm font-medium text-dm-primary" @click="showContactForm = true">
          ＋ {{ t('quotation.customerCenter.addContact') }}
        </button>
      </div>
      <div class="flex-1 space-y-3 overflow-y-auto p-5 pt-2">
        <article v-for="contact in selectedCustomer.contacts" :key="`${contact.name}-${contact.email}`" class="rounded-dm border border-dm-border bg-dm-page p-4">
          <div class="flex items-start justify-between gap-3"><h5 class="font-semibold text-dm-text">{{ contact.name }}</h5><button type="button" class="text-xs text-dm-primary">{{ t('quotation.common.edit') }}</button></div>
          <button type="button" class="mt-3 flex max-w-full items-center gap-2 truncate text-left text-sm text-dm-text-secondary hover:text-dm-primary" @click="copyContact(contact.email)"><Mail class="h-4 w-4 shrink-0" /> {{ contact.email }}</button>
          <button type="button" class="mt-2 flex items-center gap-2 text-left text-sm text-dm-text-secondary hover:text-dm-primary" @click="copyContact(contact.phone)"><Phone class="h-4 w-4 shrink-0" /> {{ contact.phone }}</button>
          <button
            type="button"
            class="mt-3 text-sm font-medium text-dm-primary hover:underline"
            @click="emit('navigateToCreate', { company: selectedCustomer.company, ...contact })"
          >
            {{ t('quotation.customerCenter.useForQuote') }}
          </button>
        </article>
      </div>
    </aside>

    <div
      v-if="customerForQuote"
      class="fixed inset-0 z-[55] flex items-center justify-center p-4"
    >
      <div class="dm-card w-full max-w-xl p-6 shadow-2xl" @click.stop>
        <div class="flex items-start justify-between">
          <div>
            <h3 class="text-xl font-bold text-dm-text">
              {{ t('quotation.customerCenter.chooseContactTitle') }}
            </h3>
            <p class="mt-1 text-sm text-dm-text-tertiary">
              {{ customerForQuote.company }} · {{ t('quotation.customerCenter.chooseContactHint') }}
            </p>
          </div>
          <button type="button" class="text-dm-text-tertiary" @click="customerForQuote = null">
            <X class="h-5 w-5" />
          </button>
        </div>
        <div class="mt-5 space-y-2">
          <button
            v-for="contact in customerForQuote.contacts"
            :key="`${contact.name}-${contact.email}`"
            type="button"
            class="flex w-full items-center justify-between rounded-dm border border-dm-border p-4 text-left transition hover:border-dm-primary hover:bg-dm-primary-bg"
            @click="useContactForQuote(customerForQuote, contact)"
          >
            <span class="min-w-0">
              <span class="block font-semibold text-dm-text">{{ contact.name }}</span>
              <span class="mt-1 block truncate text-sm text-dm-text-tertiary">{{ contact.email }}</span>
            </span>
            <span class="ml-4 shrink-0 text-sm font-medium text-dm-primary">
              {{ t('quotation.customerCenter.selectContact') }}
            </span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="showContactForm" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <form class="dm-card w-full max-w-2xl space-y-5 p-6 shadow-2xl" @submit.prevent="saveContact">
        <div class="flex items-start justify-between"><div><h3 class="text-xl font-bold text-dm-text">{{ selectedCustomer ? t('quotation.customerCenter.addContact') : t('quotation.customerCenter.addCustomer') }}</h3><p class="mt-1 text-sm text-dm-text-tertiary">{{ t('quotation.customerCenter.formHint') }}</p></div><button type="button" class="text-dm-text-tertiary" @click="closePanels"><X class="h-5 w-5" /></button></div>
        <div v-if="!selectedCustomer"><label class="block text-sm font-medium text-dm-text-secondary">{{ t('quotation.customerCenter.companyNameRequired') }}<input class="mt-1 w-full rounded-dm border border-dm-border px-3 py-2 text-sm" :placeholder="t('quotation.customerCenter.companyPlaceholder')" required /></label></div>
        <div class="grid gap-4 sm:grid-cols-2"><label class="text-sm font-medium text-dm-text-secondary">{{ t('quotation.customerCenter.contactNameRequired') }}<input v-model="contactName" class="mt-1 w-full rounded-dm border border-dm-border px-3 py-2 font-normal" :placeholder="t('quotation.customerCenter.contactNamePlaceholder')" required /></label><label class="text-sm font-medium text-dm-text-secondary">{{ t('quotation.customerCenter.role') }}<input v-model="contactRole" class="mt-1 w-full rounded-dm border border-dm-border px-3 py-2 font-normal" placeholder="Sales Manager" /></label><label class="text-sm font-medium text-dm-text-secondary">{{ t('quotation.customerCenter.emailRequired') }}<input v-model="contactEmail" type="email" class="mt-1 w-full rounded-dm border border-dm-border px-3 py-2 font-normal" placeholder="name@example.com" required /></label><label class="text-sm font-medium text-dm-text-secondary">{{ t('quotation.customerCenter.phone') }}<input v-model="contactPhone" class="mt-1 w-full rounded-dm border border-dm-border px-3 py-2 font-normal" placeholder="+60 12 345 6789" /></label></div>
        <div class="flex justify-end gap-3"><button type="button" class="dm-btn-default cursor-pointer px-4 py-2 text-sm" @click="closePanels">{{ t('quotation.common.cancel') }}</button><button type="submit" class="dm-btn-primary cursor-pointer px-4 py-2 text-sm">{{ t('quotation.common.save') }}</button></div>
      </form>
    </div>
  </section>
</template>
