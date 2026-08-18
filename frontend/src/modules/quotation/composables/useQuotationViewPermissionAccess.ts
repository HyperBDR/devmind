import { computed, ref } from 'vue'

import { useUserStore } from '@/store/user'

import {
  getViewPermissionContext,
  type ViewPermissionContext,
} from '../api/viewPermissions'

type ViewPermissionStatus = 'idle' | 'loading' | 'admin' | 'user'

const status = ref<ViewPermissionStatus>('idle')
const context = ref<ViewPermissionContext | null>(null)
const activeUserId = ref<number | null>(null)
const pendingUserId = ref<number | null>(null)
const pendingRequest = ref<Promise<boolean> | null>(null)

function userIdValue(user: unknown): number | null {
  const id = (user as { id?: unknown } | null)?.id
  return typeof id === 'number' ? id : null
}

async function requestContext(
  userId: number,
  preserveAdminState: boolean,
): Promise<boolean> {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const nextContext = await getViewPermissionContext()
      activeUserId.value = userId
      context.value = nextContext
      status.value = 'admin'
      return true
    } catch (error) {
      if (preserveAdminState || attempt === 2) {
        if (preserveAdminState) {
          throw error
        }
        activeUserId.value = userId
        context.value = null
        status.value = 'user'
        return false
      }
      await new Promise((resolve) => window.setTimeout(resolve, 250))
    }
  }

  return false
}

export function useQuotationViewPermissionAccess() {
  const userStore = useUserStore()
  const currentUserId = computed(() => userIdValue(userStore.user))
  const isAdmin = computed(
    () =>
      status.value === 'admin' &&
      activeUserId.value === currentUserId.value,
  )
  const isLoading = computed(
    () =>
      currentUserId.value !== null &&
      (status.value === 'idle' ||
        status.value === 'loading' ||
        activeUserId.value !== currentUserId.value),
  )
  const currentContext = computed(() =>
    isAdmin.value ? context.value : null,
  )

  async function ensure(force = false): Promise<boolean> {
    const userId = currentUserId.value
    if (userId === null) {
      return false
    }

    if (
      pendingRequest.value &&
      pendingUserId.value === userId
    ) {
      return pendingRequest.value
    }

    if (
      !force &&
      activeUserId.value === userId &&
      (status.value === 'admin' || status.value === 'user')
    ) {
      return status.value === 'admin'
    }

    const preserveAdminState =
      activeUserId.value === userId && status.value === 'admin'
    activeUserId.value = userId
    if (!preserveAdminState) {
      status.value = 'loading'
      context.value = null
    }

    pendingUserId.value = userId
    const request = requestContext(userId, preserveAdminState)
    pendingRequest.value = request
    try {
      return await request
    } finally {
      if (pendingRequest.value === request) {
        pendingRequest.value = null
        pendingUserId.value = null
      }
    }
  }

  return {
    context: currentContext,
    isAdmin,
    isLoading,
    ensure,
  }
}
