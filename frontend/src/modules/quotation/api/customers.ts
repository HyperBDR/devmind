import { apiRequest } from './client'

export interface CustomerContactSummary {
  name: string
  email: string
  phone: string
  recordCount: number
}

export interface CustomerSummary {
  company: string
  contacts: CustomerContactSummary[]
  recordCount: number
  updatedAt: string
}

export async function getCustomerSummary(): Promise<CustomerSummary[]> {
  const data = await apiRequest<{
    customers: Array<{
      company: string
      contacts: Array<{
        name: string
        email: string
        phone: string
        record_count: number
      }>
      record_count: number
      updated_at: string | null
    }>
  }>(
    '/customers/summary',
  )
  return data.customers.map((customer) => ({
    company: customer.company,
    contacts: customer.contacts.map((contact) => ({
      name: contact.name,
      email: contact.email,
      phone: contact.phone,
      recordCount: contact.record_count,
    })),
    recordCount: customer.record_count,
    updatedAt: customer.updated_at || '',
  }))
}
