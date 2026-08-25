import type { DiscountOption, Product, ProductLineOption, Service } from '../types'
import { apiRequest } from './client'

export interface CatalogPaymentTerm {
  value: string
  label: string
}

export interface UserQuotationCatalog {
  version: string
  initialized: boolean
  products: Product[]
  services: Service[]
  discounts: DiscountOption[]
  product_lines: ProductLineOption[]
  payment_terms: CatalogPaymentTerm[]
  updated_at?: string
}

export type UserQuotationCatalogPayload = Omit<
  UserQuotationCatalog,
  'initialized' | 'updated_at'
>

function normalizeCatalogItem<T>(item: T): T {
  const raw = item as T & {
    list_price?: unknown
    listPrice?: unknown
  }
  if (raw.list_price === undefined || raw.listPrice !== undefined) return item
  return {
    ...item,
    listPrice: Number(raw.list_price || 0),
  } as T
}

function normalizeCatalog(catalog: UserQuotationCatalog): UserQuotationCatalog {
  return {
    ...catalog,
    products: catalog.products.map((item) => normalizeCatalogItem(item)),
    services: catalog.services.map((item) => normalizeCatalogItem(item)),
  }
}

export async function getCatalog(): Promise<UserQuotationCatalog> {
  return normalizeCatalog(await apiRequest<UserQuotationCatalog>('/catalog'))
}

export async function updateCatalog(
  payload: UserQuotationCatalogPayload,
): Promise<UserQuotationCatalog> {
  return normalizeCatalog(await apiRequest<UserQuotationCatalog>('/catalog', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }))
}

export async function importLegacyCatalog(
  payload: UserQuotationCatalogPayload,
): Promise<{ imported: boolean; catalog: UserQuotationCatalog }> {
  const result = await apiRequest<{
    imported: boolean
    catalog: UserQuotationCatalog
  }>(
    '/catalog/import-legacy',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
  return { ...result, catalog: normalizeCatalog(result.catalog) }
}
