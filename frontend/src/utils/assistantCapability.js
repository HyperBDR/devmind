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
