<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ShieldCheck, UserCog } from 'lucide-vue-next'

import type {
  QuotationMembershipContext,
  QuotationMembershipRecord,
  QuotationMembershipRole
} from '../api/viewPermissions'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import FormSelect, { type FormSelectOption } from './FormSelect.vue'

const props = defineProps<{
  context: QuotationMembershipContext
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  assign: [userId: number, role: QuotationMembershipRole]
  change: [membershipId: number, role: QuotationMembershipRole]
}>()

const { t } = useQuotationI18n()
const roleDrafts = reactive<Record<number, QuotationMembershipRole>>({})

const roleOptions = computed<FormSelectOption[]>(() => [
  {
    value: 'quotation_user',
    label: t('quotation.pages.permissions.quotationUser')
  },
  {
    value: 'quotation_admin',
    label: t('quotation.pages.permissions.quotationAdmin')
  }
])

watch(
  () => props.context.members,
  (members) => {
    for (const member of members) {
      roleDrafts[member.user_id] = member.role || 'quotation_user'
    }
  },
  { immediate: true }
)

function selectedRole(member: QuotationMembershipRecord) {
  return roleDrafts[member.user_id] || 'quotation_user'
}

function assignRole(member: QuotationMembershipRecord) {
  emit('assign', member.user_id, selectedRole(member))
}

function changeRole(member: QuotationMembershipRecord) {
  if (member.id === null) return
  emit('change', member.id, selectedRole(member))
}

function roleChanged(member: QuotationMembershipRecord) {
  return member.role !== selectedRole(member)
}
</script>

<template>
  <section
    class="dm-card overflow-hidden"
    aria-labelledby="user-permissions-title"
  >
    <div class="border-b border-dm-border-light bg-dm-surface px-4 py-3">
      <div class="flex items-center gap-2">
        <UserCog class="h-4 w-4 text-dm-primary" />
        <h3 id="user-permissions-title" class="font-semibold">
          {{ t('quotation.pages.permissions.userPermissionsTitle') }}
        </h3>
      </div>
      <p class="mt-1 text-sm text-dm-text-secondary">
        {{ t('quotation.pages.permissions.userPermissionsSubtitle') }}
      </p>
    </div>

    <div
      v-if="loading"
      class="px-4 py-8 text-center text-sm text-dm-text-secondary"
    >
      {{ t('quotation.common.loading') }}
    </div>
    <div
      v-else-if="context.members.length === 0"
      class="px-4 py-8 text-center text-sm text-dm-text-secondary"
    >
      {{ t('quotation.pages.permissions.noManagedUsers') }}
    </div>
    <div v-else class="overflow-x-auto">
      <table class="dm-table min-w-[760px]">
        <thead class="bg-dm-surface text-dm-text-secondary">
          <tr>
            <th>{{ t('quotation.pages.permissions.userColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.roleColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.assignedByColumn') }}</th>
            <th class="text-right">
              {{ t('quotation.pages.permissions.actionsColumn') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="member in context.members" :key="member.user_id">
            <td>
              <div class="font-medium">{{ member.name }}</div>
              <div class="text-xs text-dm-text-secondary">
                {{ member.email || member.username }}
              </div>
            </td>
            <td class="w-64">
              <FormSelect
                v-model="roleDrafts[member.user_id]"
                :options="roleOptions"
                :aria-label="t('quotation.pages.permissions.roleColumn')"
              />
            </td>
            <td class="text-dm-text-secondary">
              {{ member.assigned_by || '—' }}
            </td>
            <td class="text-right">
              <button
                v-if="member.id === null"
                type="button"
                class="dm-btn-primary px-3 py-2 text-sm"
                :disabled="saving"
                @click="assignRole(member)"
              >
                <ShieldCheck class="h-4 w-4" />
                {{ t('quotation.pages.permissions.assignRole') }}
              </button>
              <button
                v-else
                type="button"
                class="dm-btn-default px-3 py-2 text-sm"
                :disabled="saving || !roleChanged(member)"
                @click="changeRole(member)"
              >
                {{ t('quotation.pages.permissions.changeRole') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
