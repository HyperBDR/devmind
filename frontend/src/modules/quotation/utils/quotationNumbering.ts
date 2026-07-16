import type { ProductLineOption, Quotation, QuoteProductLine } from '../types';

export const PRODUCT_LINE_OPTIONS: ProductLineOption[] = [
  { value: 'BDR', label: 'HyperBDR' },
  { value: 'Motion', label: 'HyperMotion' },
  { value: 'AGIOne', label: 'AGIOne' },
  { value: 'Service', label: 'General Service' },
];

export const CUSTOM_PRODUCT_LINE_STORAGE_KEY = 'qmp_custom_product_line_options_v2';
const LEGACY_PRODUCT_LINE_STORAGE_KEY = 'qmp_product_line_options';

export function isDefaultProductLine(value: QuoteProductLine): boolean {
  return PRODUCT_LINE_OPTIONS.some(option => normalize(option.value) === normalize(value));
}

export function mergeProductLineOptions(customOptions: ProductLineOption[] = []): ProductLineOption[] {
  const merged = [...PRODUCT_LINE_OPTIONS];
  customOptions.forEach(option => {
    if (!merged.some(item => normalize(item.value) === normalize(option.value))) {
      merged.push(option);
    }
  });
  return merged;
}

export function extractCustomProductLineOptions(options: ProductLineOption[]): ProductLineOption[] {
  return options.filter(option => !isDefaultProductLine(option.value as QuoteProductLine));
}

export function loadProductLineOptions(): ProductLineOption[] {
  if (typeof window === 'undefined') {
    return PRODUCT_LINE_OPTIONS;
  }

  try {
    const savedCustom = localStorage.getItem(CUSTOM_PRODUCT_LINE_STORAGE_KEY);
    if (savedCustom) {
      const custom = JSON.parse(savedCustom);
      if (Array.isArray(custom)) {
        return mergeProductLineOptions(custom);
      }
    }

    const legacy = localStorage.getItem(LEGACY_PRODUCT_LINE_STORAGE_KEY);
    if (legacy) {
      localStorage.removeItem(LEGACY_PRODUCT_LINE_STORAGE_KEY);
    }
  } catch {
    // ignore invalid storage
  }

  return PRODUCT_LINE_OPTIONS;
}

export function saveCustomProductLineOptions(allOptions: ProductLineOption[]): void {
  if (typeof window === 'undefined') return;
  const custom = extractCustomProductLineOptions(allOptions);
  localStorage.setItem(CUSTOM_PRODUCT_LINE_STORAGE_KEY, JSON.stringify(custom));
}

export interface ProductLineDeletionState {
  canDelete: boolean;
  reason: string;
  usageCount: number;
}

export const PRODUCT_LINE_PREFIX_RULE = '2-12 letters or numbers, starting with a letter';
const PRODUCT_LINE_PREFIX_PATTERN = /^[A-Za-z][A-Za-z0-9]{1,11}$/;

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

function normalizeSequenceRoot(value: string): string {
  return normalize(value.replace(/_R\d+$/i, ''));
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function isProductLinePrefixValid(value: string): boolean {
  return PRODUCT_LINE_PREFIX_PATTERN.test(value.trim());
}

export function isProductLinePrefixUnique(value: string, options: ProductLineOption[]): boolean {
  const target = normalize(value);
  return !!target && !options.some(option => normalize(option.value) === target);
}

export function getProductLineDeletionState(
  productLine: QuoteProductLine,
  options: ProductLineOption[],
  quotations: Pick<Quotation, 'productLine' | 'quoteNo'>[]
): ProductLineDeletionState {
  const target = normalize(productLine);
  const exists = options.some(option => normalize(option.value) === target);
  const usageCount = quotations.filter(quote => {
    const quoteProductLine = quote.productLine || inferProductLineFromQuoteNumber(quote.quoteNo, options);
    return normalize(quoteProductLine) === target;
  }).length;

  if (!exists) {
    return { canDelete: false, reason: '该产品线不存在', usageCount };
  }
  if (isDefaultProductLine(productLine)) {
    return { canDelete: false, reason: '默认产品线不能删除', usageCount };
  }
  if (usageCount > 0) {
    return {
      canDelete: true,
      reason: `已有 ${usageCount} 条报价使用该产品线，删除后历史报价不受影响`,
      usageCount,
    };
  }
  return { canDelete: true, reason: '', usageCount };
}

export function buildQuoteNumberBase(productLine: QuoteProductLine, date: Date): string {
  return `${productLine}${pad2(date.getDate())}${pad2(date.getMonth() + 1)}${String(date.getFullYear()).slice(-2)}`;
}

export function dateFromInput(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return new Date();
  return new Date(year, month - 1, day);
}

export function getNextAutoQuoteNumber(productLine: QuoteProductLine, date: Date, existingNumbers: string[]): string {
  const base = buildQuoteNumberBase(productLine, date);
  const normalizedExisting = new Set(existingNumbers.map(normalizeSequenceRoot));
  if (!normalizedExisting.has(normalize(base))) return base;

  let suffix = 1;
  while (normalizedExisting.has(normalize(`${base}.${suffix}`))) {
    suffix += 1;
  }
  return `${base}.${suffix}`;
}

export function getNextRevisionQuoteNumber(currentQuoteNumber: string, existingNumbers: string[]): string {
  const root = currentQuoteNumber.trim().replace(/_R\d+$/i, '');
  const normalizedExisting = new Set(existingNumbers.map(normalize));
  let revision = 1;
  while (normalizedExisting.has(normalize(`${root}_R${revision}`))) {
    revision += 1;
  }
  return `${root}_R${revision}`;
}

export function inferProductLineFromQuoteNumber(
  quoteNumber: string,
  options: ProductLineOption[] = PRODUCT_LINE_OPTIONS
): QuoteProductLine {
  const trimmed = quoteNumber.trim();
  const found = [...options]
    .sort((a, b) => b.value.length - a.value.length)
    .find(option => new RegExp(`^${escapeRegex(option.value)}\\d{6}(?:\\.\\d+)?(?:_R\\d+)?$`, 'i').test(trimmed));
  if (found) return found.value;

  const match = trimmed.match(/^([A-Za-z][A-Za-z0-9]{1,11})\d{6}(?:\.\d+)?(?:_R\d+)?$/i);
  return match?.[1] || 'BDR';
}

export function isQuotationNumberUnique(
  quoteNumber: string,
  quotations: Pick<Quotation, 'id' | 'quoteNo'>[],
  currentQuoteId?: string
): boolean {
  const target = normalize(quoteNumber);
  if (!target) return false;
  return !quotations.some(quote => quote.id !== currentQuoteId && normalize(quote.quoteNo) === target);
}
