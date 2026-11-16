export function calculateInvoiceTotals(
  items: { quantity: number; unitPrice: number }[], taxRate: number,
) {
  const scaled = (value: number) => BigInt(Math.round(Number(value) * 10000))
  const rate = scaled(taxRate)
  let subtotal = 0n
  let tax = 0n
  for (const item of items) {
    const net = (scaled(item.quantity) * scaled(item.unitPrice) + 500000n) / 1000000n
    subtotal += net
    tax += (net * rate + 500000n) / 1000000n
  }
  return {
    subtotal: Number(subtotal) / 100,
    tax: Number(tax) / 100,
    total: Number(subtotal + tax) / 100,
  }
}
