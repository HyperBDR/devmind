import type {
  ItemType,
  Product,
  Quotation,
  QuotationLineItem,
  Service,
} from '../types'

export interface DescriptionHistoryOption {
  value: string
  label?: string
  key: string
  meta?: {
    listPrice?: number
    source: 'catalog' | 'quote'
  }
}

function normalize(value: string): string {
  return value.trim().toLowerCase()
}

function descriptionText(item: {
  description?: string
  name?: string
}): string {
  return (item.description || item.name || '').trim()
}

function isSoftwareType(type: ItemType): boolean {
  return type === 'Software'
}

/**
 * Build selectable description history for a line-item category.
 * Prefers Catalog entries, then past quotation line descriptions.
 */
export function buildDescriptionHistoryOptions(
  itemType: ItemType,
  products: Product[],
  services: Service[],
  quotations: Array<Pick<Quotation, 'items' | 'createdAt'>>,
): DescriptionHistoryOption[] {
  const options: DescriptionHistoryOption[] = []
  const seen = new Set<string>()

  const pushOption = (
    text: string,
    meta: DescriptionHistoryOption['meta'],
    label?: string,
  ) => {
    const trimmed = text.trim()
    const key = normalize(trimmed)
    if (!key || seen.has(key)) return
    seen.add(key)
    options.push({
      value: trimmed,
      label,
      key: `${meta?.source || 'catalog'}:${key}`,
      meta,
    })
  }

  if (isSoftwareType(itemType)) {
    products.forEach((product) => {
      const text = descriptionText(product)
      if (!text) return
      pushOption(text, {
        listPrice: product.listPrice,
        source: 'catalog',
      })
    })
  } else {
    services.forEach((service) => {
      const text = descriptionText(service)
      if (!text) return
      pushOption(text, {
        listPrice: service.listPrice,
        source: 'catalog',
      })
    })
  }

  const quoteItems = quotations
    .slice()
    .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
    .flatMap((quote) => quote.items || [])
    .filter((item) =>
      isSoftwareType(itemType)
        ? item.type === 'Software'
        : item.type !== 'Software',
    )

  quoteItems.forEach((item) => {
    const text = descriptionText(item)
    if (!text) return
    pushOption(
      text,
      {
        listPrice: item.listPrice,
        source: 'quote',
      },
      item.listPrice ? `List ${item.listPrice}` : undefined,
    )
  })

  return options
}

function buildAutoCode(prefix: string): string {
  return `${prefix}-${Date.now().toString(36).toUpperCase().slice(-7)}`
}

/**
 * Persist new line-item descriptions into Catalog by category.
 * Software -> products, Others -> services. Existing texts are skipped.
 */
export function upsertDescriptionsToCatalog(
  items: QuotationLineItem[],
  products: Product[],
  services: Service[],
  productLineLabel = 'HyperBDR',
): { products: Product[]; services: Service[]; added: number } {
  const nextProducts = [...products]
  const nextServices = [...services]
  let added = 0
  const category = productLineLabel.trim() || 'HyperBDR'

  const productKeys = new Set(
    nextProducts.map((item) => normalize(descriptionText(item))).filter(Boolean),
  )
  const serviceKeys = new Set(
    nextServices.map((item) => normalize(descriptionText(item))).filter(Boolean),
  )

  items.forEach((item, index) => {
    const text = descriptionText(item)
    if (!text) return
    const key = normalize(text)

    if (item.type === 'Software') {
      if (productKeys.has(key)) return
      productKeys.add(key)
      nextProducts.push({
        id: `prod-auto-${Date.now()}-${index}`,
        name: text.slice(0, 120),
        code: buildAutoCode('SW'),
        listPrice: Number(item.listPrice) || 0,
        category,
        description: text,
      })
      added += 1
      return
    }

    if (serviceKeys.has(key)) return
    serviceKeys.add(key)
    nextServices.push({
      id: `serv-auto-${Date.now()}-${index}`,
      name: text.slice(0, 120),
      code: buildAutoCode('OT'),
      listPrice: Number(item.listPrice) || 0,
      unit: 'item',
      description: text,
    })
    added += 1
  })

  return {
    products: nextProducts,
    services: nextServices,
    added,
  }
}
