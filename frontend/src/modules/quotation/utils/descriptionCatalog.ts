import type {
  ItemType,
  LineItemCurrency,
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
    itemId?: string
    itemName?: string
    listPrice?: number
    prices?: Partial<Record<LineItemCurrency, number>>
    currency?: Quotation['currency']
    source: 'catalog' | 'quote'
  }
}

export function catalogPriceForCurrency(
  item: Pick<Product | Service, 'listPrice' | 'currency' | 'prices'>,
  currency: LineItemCurrency,
): number | undefined {
  const prices = item.prices as Record<string, number> | undefined
  const value = prices?.[currency] ?? prices?.[currency.toLowerCase()]
  if (value !== undefined) return Number(value)
  if ((item.currency || 'USD') === currency) return Number(item.listPrice)
  return undefined
}

export interface LineItemDescriptionHistory {
  type: ItemType
  description: string
  listPrice: number
  currency: Quotation['currency']
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
  quotations: Array<Pick<Quotation, 'items' | 'createdAt' | 'currency'>>,
  currency: Quotation['currency'] = 'USD',
  lineItemHistory: LineItemDescriptionHistory[] = [],
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
      const itemCurrency = (currency || product.currency || 'USD') as LineItemCurrency
      const listPrice = catalogPriceForCurrency(product, itemCurrency)
      pushOption(text, {
        itemId: product.id,
        itemName: product.name,
        listPrice,
        prices: product.prices,
        currency: itemCurrency,
        source: 'catalog',
      }, listPrice
        ? `${itemCurrency} ${listPrice.toLocaleString('en-US')}`
        : product.pricingNote)
    })
  } else {
    services.forEach((service) => {
      const text = descriptionText(service)
      if (!text) return
      const itemCurrency = (currency || service.currency || 'USD') as LineItemCurrency
      const listPrice = catalogPriceForCurrency(service, itemCurrency)
      pushOption(text, {
        itemId: service.id,
        itemName: service.name,
        listPrice,
        prices: service.prices,
        currency: itemCurrency,
        source: 'catalog',
      }, listPrice
        ? `${itemCurrency} ${listPrice.toLocaleString('en-US')}`
        : service.pricingNote)
    })
  }

  lineItemHistory
    .filter((item) =>
      item.currency === currency
      && (isSoftwareType(itemType)
        ? item.type === 'Software'
        : item.type !== 'Software'),
    )
    .forEach((item) => {
      pushOption(
        item.description,
        {
          listPrice: item.listPrice,
          currency: item.currency,
          source: 'quote',
        },
        item.listPrice
          ? `${item.currency} ${item.listPrice.toLocaleString('en-US')}`
          : undefined,
      )
    })

  const quoteItems = quotations
    .slice()
    .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
    .flatMap((quote) =>
      (quote.items || []).map((item) => ({
        item,
        currency: quote.currency,
      })),
    )
    .filter(({ item, currency: quoteCurrency }) =>
      quoteCurrency === currency && (
      isSoftwareType(itemType)
        ? item.type === 'Software'
        : item.type !== 'Software'
      ),
    )

  quoteItems.forEach(({ item, currency: quoteCurrency }) => {
    const text = descriptionText(item)
    if (!text) return
    pushOption(
      text,
      {
        listPrice: item.listPrice,
        currency: quoteCurrency,
        source: 'quote',
      },
      item.listPrice
        ? `${quoteCurrency} ${item.listPrice.toLocaleString('en-US')}`
        : undefined,
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
  currency: Quotation['currency'] = 'USD',
): { products: Product[]; services: Service[]; added: number } {
  const nextProducts = [...products]
  const nextServices = [...services]
  let added = 0
  const category = productLineLabel.trim() || 'HyperBDR'

  const productKeys = new Set(
    nextProducts
      .map((item) => normalize(descriptionText(item)))
      .filter(Boolean),
  )
  const serviceKeys = new Set(
    nextServices
      .map((item) => normalize(descriptionText(item)))
      .filter(Boolean),
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
        currency,
        prices: { [currency as LineItemCurrency]: Number(item.listPrice) || 0 },
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
      currency,
      prices: { [currency as LineItemCurrency]: Number(item.listPrice) || 0 },
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
