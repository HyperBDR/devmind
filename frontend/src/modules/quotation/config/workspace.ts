export const QUOTE_DESK_ROUTES = {
  dashboard: '/quotation/dashboard',
  list: '/quotation/list',
  create: '/quotation/create',
  catalog: '/quotation/catalog',
  audit: '/quotation/audit',
  permissions: '/quotation/permissions',
  customers: '/quotation/customers',
} as const

export type QuoteDeskTab = keyof typeof QUOTE_DESK_ROUTES | 'details'

export function quotationTabFromPath(path: string): QuoteDeskTab {
  if (path.startsWith('/quotation/details/')) return 'details'
  if (path.startsWith('/quotation/list')) return 'list'
  if (path.startsWith('/quotation/create')) return 'create'
  if (path.startsWith('/quotation/imports')) return 'list'
  if (path.startsWith('/quotation/catalog')) return 'catalog'
  if (path.startsWith('/quotation/audit')) return 'audit'
  if (path.startsWith('/quotation/permissions')) return 'permissions'
  if (path.startsWith('/quotation/customers')) return 'customers'
  return 'dashboard'
}
