export function projectBusinessScope(project = {}) {
  const businessScope = String(project.domestic_type || '').toLowerCase()

  if (businessScope.includes('海外') || businessScope.includes('oversea')) {
    return 'overseas'
  }
  if (businessScope.includes('国内') || businessScope.includes('domestic')) {
    return 'domestic'
  }

  const sourceScope = String(project.project_scope || '').toLowerCase()
  if (sourceScope.includes('oversea')) return 'overseas'
  if (sourceScope.includes('domestic')) return 'domestic'
  return 'unknown'
}

export function isDomesticProject(project) {
  return projectBusinessScope(project) === 'domestic'
}

export function isOverseasProject(project) {
  return projectBusinessScope(project) === 'overseas'
}
