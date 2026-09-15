type ColumnScope = 'quote' | 'invoice'

const STORAGE_PREFIX = 'quote-desk.visible-columns.v1'

function storageKey(scope: ColumnScope): string {
  return `${STORAGE_PREFIX}.${scope}`
}

export function loadVisibleColumns<T extends string>(
  scope: ColumnScope,
  availableColumns: readonly T[],
  defaultColumns: readonly T[],
): T[] {
  if (typeof window === 'undefined') return [...defaultColumns]
  try {
    const value = JSON.parse(
      window.localStorage.getItem(storageKey(scope)) || 'null',
    )
    if (!Array.isArray(value)) return [...defaultColumns]
    const available = new Set<string>(availableColumns)
    const columns = Array.from(
      new Set(value.filter((key): key is T => available.has(key))),
    )
    return columns.length || value.length === 0
      ? columns
      : [...defaultColumns]
  } catch {
    return [...defaultColumns]
  }
}

export function saveVisibleColumns(
  scope: ColumnScope,
  columns: readonly string[],
): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(storageKey(scope), JSON.stringify(columns))
}
