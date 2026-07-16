export const DEFAULT_TAX_LABEL = 'VAT';
export const TAX_LABEL_HISTORY_KEY = 'qmp_tax_label_history';
const MAX_TAX_LABEL_HISTORY = 12;
type TaxLabelSource = { taxLabel?: string; createdAt?: string; createdByEmail?: string };

function getTaxLabelHistoryStorageKey(userEmail?: string): string {
  const normalizedEmail = userEmail?.trim().toLowerCase();
  return normalizedEmail ? `${TAX_LABEL_HISTORY_KEY}:${normalizedEmail}` : TAX_LABEL_HISTORY_KEY;
}

export function normalizeTaxLabel(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

export function getTaxLabelHistory(userEmail?: string): string[] {
  if (typeof window === 'undefined') {
    return [DEFAULT_TAX_LABEL];
  }

  try {
    const saved = localStorage.getItem(getTaxLabelHistoryStorageKey(userEmail));
    const parsed = saved ? JSON.parse(saved) : [];
    if (!Array.isArray(parsed)) return [DEFAULT_TAX_LABEL];

    const labels = parsed
      .map(item => normalizeTaxLabel(String(item)))
      .filter(Boolean);

    return labels.length > 0 ? labels : [DEFAULT_TAX_LABEL];
  } catch {
    return [DEFAULT_TAX_LABEL];
  }
}

export function getTaxLabelHistoryFromQuotations(
  quotations: TaxLabelSource[],
  userEmail?: string,
): string[] {
  const normalizedEmail = userEmail?.trim().toLowerCase();
  const scoped = normalizedEmail
    ? quotations.filter(q => (q.createdByEmail || '').trim().toLowerCase() === normalizedEmail)
    : quotations;

  const fromQuotes = [...scoped]
    .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
    .map(q => normalizeTaxLabel(q.taxLabel || ''))
    .filter(Boolean);

  return fromQuotes;
}

export function getMergedTaxLabelHistory(
  userEmail: string | undefined,
  quotations: TaxLabelSource[],
): string[] {
  const merged = [
    ...getTaxLabelHistoryFromQuotations(quotations, userEmail),
    ...getTaxLabelHistory(userEmail),
  ];
  const unique = Array.from(new Set(merged.map(label => normalizeTaxLabel(label)).filter(Boolean)));
  return unique.length > 0 ? unique.slice(0, MAX_TAX_LABEL_HISTORY) : [DEFAULT_TAX_LABEL];
}

export function rememberTaxLabel(value: string, userEmail?: string): string[] {
  const normalized = normalizeTaxLabel(value) || DEFAULT_TAX_LABEL;
  const history = getTaxLabelHistory(userEmail).filter(label => label !== normalized);
  const nextHistory = [normalized, ...history].slice(0, MAX_TAX_LABEL_HISTORY);

  if (typeof window !== 'undefined') {
    localStorage.setItem(getTaxLabelHistoryStorageKey(userEmail), JSON.stringify(nextHistory));
  }

  return nextHistory;
}

export function resolveTaxLabel(value?: string): string {
  return normalizeTaxLabel(value || '') || DEFAULT_TAX_LABEL;
}
