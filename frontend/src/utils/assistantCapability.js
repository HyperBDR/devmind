export function indexAssistantCapabilities(items) {
  const capabilities = new Map()
  for (const item of items || []) {
    const appKey = item?.appKey || item?.app_key || ''
    if (!appKey) continue
    capabilities.set(appKey, {
      appKey,
      description: item.description || '',
      displayName: item.displayName || item.display_name || appKey,
      icon: item.icon || '',
      profile: item.profile || {},
      skillCount: item.skillCount ?? item.skill_count ?? 0,
      version: item.version || '1'
    })
  }
  return capabilities
}

export function resolveAssistantCapability(capabilities, appKey) {
  if (!appKey || !capabilities?.get) return null
  return capabilities.get(appKey) || null
}

export function localizeAssistantCapability(
  capability,
  translate,
  hasTranslation
) {
  const profileKeys = capability?.profile?.ui_i18n || {}
  const fallbackTitle = capability?.displayName || capability?.appKey || ''
  const title = translateIfAvailable(
    profileKeys.title_key,
    fallbackTitle,
    translate,
    hasTranslation
  )

  return {
    description: translateIfAvailable(
      profileKeys.description_key,
      capability?.description || '',
      translate,
      hasTranslation
    ),
    drawerLabel: translateIfAvailable(
      profileKeys.drawer_label_key,
      title,
      translate,
      hasTranslation
    ),
    openLabel: translateIfAvailable(
      profileKeys.open_label_key,
      title,
      translate,
      hasTranslation
    ),
    title
  }
}

function translateIfAvailable(key, fallback, translate, hasTranslation) {
  if (
    !key ||
    typeof translate !== 'function' ||
    typeof hasTranslation !== 'function' ||
    !hasTranslation(key)
  ) {
    return fallback
  }
  return translate(key)
}
