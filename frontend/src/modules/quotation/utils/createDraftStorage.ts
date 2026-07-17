import type {
  PaymentTermOption,
  QuotationLineItem,
  QuoteProductLine,
} from '../types';

const CREATE_DRAFT_PREFIX = 'qmp_create_quote_draft_';
const DRAFT_VERSION = 1;
const DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export interface CreateQuoteDraft {
  version: number;
  savedAt: string;
  quoteNo: string;
  quoteNoMode: 'auto' | 'custom';
  productLine: QuoteProductLine;
  projectName: string;
  clientCompany: string;
  contactPerson: string;
  email: string;
  billingCompany: string;
  billingContact: string;
  billingEmail: string;
  region: string;
  industry: string;
  salesperson: string;
  currency: 'CNY' | 'USD' | 'EUR';
  paymentTermOption: PaymentTermOption;
  paymentTermsCustom: string;
  vatRateInput: string;
  taxLabel: string;
  quoteDate: string;
  expireDate: string;
  remarksDisclaimer: string;
  issuerCompanyName: string;
  issuerContactName: string;
  issuerContactEmail: string;
  issuerContactTitle: string;
  issuerSignature: string;
  items: QuotationLineItem[];
}

function storageKey(email: string): string {
  return `${CREATE_DRAFT_PREFIX}${email.trim().toLowerCase()}`;
}

export function isCreateQuoteDraftMeaningful(
  draft: Partial<CreateQuoteDraft> | null | undefined,
): boolean {
  if (!draft) return false;
  if (
    draft.projectName?.trim() ||
    draft.clientCompany?.trim() ||
    draft.contactPerson?.trim() ||
    draft.email?.trim() ||
    draft.billingCompany?.trim() ||
    draft.billingContact?.trim() ||
    draft.billingEmail?.trim() ||
    draft.remarksDisclaimer?.trim() ||
    draft.paymentTermsCustom?.trim() ||
    draft.vatRateInput?.trim()
  ) {
    return true;
  }
  return (draft.items || []).some(
    (item) =>
      Boolean(item.description?.trim() || item.name?.trim() || item.itemId?.trim()) ||
      Number(item.listPrice) > 0 ||
      Number(item.extendedPrice) > 0 ||
      Number(item.qty) > 1,
  );
}

export function loadCreateQuoteDraft(
  email?: string | null,
): CreateQuoteDraft | null {
  if (!email || typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(storageKey(email));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CreateQuoteDraft;
    if (!parsed || parsed.version !== DRAFT_VERSION) {
      clearCreateQuoteDraft(email);
      return null;
    }
    const savedAt = Date.parse(parsed.savedAt);
    if (!Number.isFinite(savedAt) || Date.now() - savedAt > DRAFT_MAX_AGE_MS) {
      clearCreateQuoteDraft(email);
      return null;
    }
    if (!isCreateQuoteDraftMeaningful(parsed)) {
      clearCreateQuoteDraft(email);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveCreateQuoteDraft(
  email: string | null | undefined,
  draft: Omit<CreateQuoteDraft, 'version' | 'savedAt'>,
): void {
  if (!email || typeof window === 'undefined') return;
  if (!isCreateQuoteDraftMeaningful(draft)) {
    clearCreateQuoteDraft(email);
    return;
  }
  try {
    const payload: CreateQuoteDraft = {
      ...draft,
      version: DRAFT_VERSION,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(storageKey(email), JSON.stringify(payload));
  } catch {
    // Ignore quota / private-mode write failures.
  }
}

export function clearCreateQuoteDraft(email?: string | null): void {
  if (!email || typeof window === 'undefined') return;
  try {
    localStorage.removeItem(storageKey(email));
  } catch {
    // Ignore storage failures.
  }
}
