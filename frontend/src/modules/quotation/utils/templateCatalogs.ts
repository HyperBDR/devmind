export function formatCatalogPrice(value: number, pricingNote?: string): string {
  if (value > 0) {
    return `USD ${value.toLocaleString(undefined, {
      maximumFractionDigits: 2,
    })}`
  }
  return pricingNote || 'Contact Sales'
}
