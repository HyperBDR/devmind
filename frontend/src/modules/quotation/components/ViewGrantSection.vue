<script setup lang="ts">
import type {
  GrantViewPermissionPayload,
  ViewPermissionContext
} from '../api/viewPermissions'
import ViewGrantForm from './ViewGrantForm.vue'
import ViewGrantTable from './ViewGrantTable.vue'

defineProps<{
  context: ViewPermissionContext
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  grant: [payload: GrantViewPermissionPayload]
  updateExpiry: [permissionId: number, expiresAt: string | null]
  revoke: [permissionId: number]
  invalid: []
}>()

function updateExpiry(permissionId: number, expiresAt: string | null) {
  emit('updateExpiry', permissionId, expiresAt)
}
</script>

<template>
  <section class="space-y-4" aria-labelledby="view-grants-title">
    <ViewGrantForm
      :context="context"
      :loading="loading"
      :saving="saving"
      @grant="emit('grant', $event)"
      @invalid="emit('invalid')"
    />
    <ViewGrantTable
      :permissions="context.permissions"
      :loading="loading"
      :saving="saving"
      @update-expiry="updateExpiry"
      @revoke="emit('revoke', $event)"
    />
  </section>
</template>
