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

export function getCatalog(): Promise<UserQuotationCatalog> {
  return apiRequest<UserQuotationCatalog>('/catalog')
}

export function updateCatalog(
  payload: UserQuotationCatalogPayload,
): Promise<UserQuotationCatalog> {
  return apiRequest<UserQuotationCatalog>('/catalog', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function importLegacyCatalog(
  payload: UserQuotationCatalogPayload,
): Promise<{ imported: boolean; catalog: UserQuotationCatalog }> {
  return apiRequest<{ imported: boolean; catalog: UserQuotationCatalog }>(
    '/catalog/import-legacy',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}
