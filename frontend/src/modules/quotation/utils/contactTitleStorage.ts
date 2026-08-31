const CONTACT_TITLE_STORAGE_PREFIX = 'qmp_user_contact_title_'

function storageKey(email: string): string {
  return `${CONTACT_TITLE_STORAGE_PREFIX}${email.trim().toLowerCase()}`
}

export function getSavedContactTitle(email?: string | null): string {
  if (!email || typeof window === 'undefined') return ''

  try {
    return localStorage.getItem(storageKey(email))?.trim() || ''
  } catch {
    return ''
  }
}

export function saveContactTitle(
  email: string | null | undefined,
  title: string | null | undefined,
): void {
  if (!email || typeof window === 'undefined') return

  const normalizedTitle = title?.trim() || ''
  if (!normalizedTitle) return

  try {
    localStorage.setItem(storageKey(email), normalizedTitle)
  } catch {
    // Ignore storage failures and keep quotation saving successful.
  }
}
