import type { QuotationLineItem } from '../types';

export interface LinePriceInput {
  listPrice: number;
  discountPercent: number;
  qty: number;
}

export interface CalculatedLinePrices {
  netUnitPrice: number;
  extendedPrice: number;
}

export interface QuotationTotals {
  softwareSubtotal: number;
  othersSubtotal: number;
  subtotalBeforeVat: number;
  vatRate: number;
  vatAmount: number;
  grandTotal: number;
}

export function roundMoney(value: number): number {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

export function parseVatRateInput(
  value: string | number | null | undefined,
): number {
  if (value === null || value === undefined) return 0
  const trimmed = String(value).trim()
  if (!trimmed) return 0
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

export function formatVatRateForInput(value?: number): string {
  if (value === undefined || value === null || value === 0) return '';
  return String(value);
}

export function normalizeVatRate(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, roundMoney(value)));
}

export function calculateLineItemPrices(input: LinePriceInput): CalculatedLinePrices {
  const listPrice = Math.max(0, Number(input.listPrice) || 0);
  const discountPercent = Math.min(100, Math.max(0, Number(input.discountPercent) || 0));
  const qty = Math.max(1, Number(input.qty) || 1);
  const netUnitPrice = roundMoney(listPrice * (1 - discountPercent / 100));

  return {
    netUnitPrice,
    extendedPrice: roundMoney(netUnitPrice * qty),
  };
}

export function calculateQuotationTotals(items: QuotationLineItem[], vatRateValue: number): QuotationTotals {
  const softwareSubtotal = roundMoney(
    items
      .filter(item => item.type === 'Software')
      .reduce((sum, item) => sum + (Number(item.extendedPrice) || 0), 0)
  );
  const othersSubtotal = roundMoney(
    items
      .filter(item => item.type !== 'Software')
      .reduce((sum, item) => sum + (Number(item.extendedPrice) || 0), 0)
  );
  const subtotalBeforeVat = roundMoney(softwareSubtotal + othersSubtotal);
  const vatRate = normalizeVatRate(vatRateValue);
  const vatAmount = roundMoney(subtotalBeforeVat * vatRate / 100);

  return {
    softwareSubtotal,
    othersSubtotal,
    subtotalBeforeVat,
    vatRate,
    vatAmount,
    grandTotal: roundMoney(subtotalBeforeVat + vatAmount),
  };
}
