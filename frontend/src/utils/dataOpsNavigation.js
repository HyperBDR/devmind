export const DATA_OPS_SECTIONS = Object.freeze([
  'executive',
  'pipeline',
  'contracts',
  'sales',
  'observations',
  'sync',
  'config'
])

const supportedSections = new Set(DATA_OPS_SECTIONS)

export function resolveDataOpsSection(section) {
  return supportedSections.has(section) ? section : 'executive'
}

export function dataOpsSectionPath(section) {
  const resolvedSection = resolveDataOpsSection(section)
  return resolvedSection === 'executive'
    ? '/data-ops'
    : `/data-ops/${resolvedSection}`
}
