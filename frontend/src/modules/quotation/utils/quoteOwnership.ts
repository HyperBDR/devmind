import type { Quotation } from '../types';

export interface QuoteUserRef {
  email: string;
  name?: string;
}

type QuoteOwnershipSource = Pick<Quotation, 'createdByEmail' | 'issuerContactEmail' | 'salesperson'>;

export function resolveQuoteOwnerEmail(quote: QuoteOwnershipSource): string {
  return quote.createdByEmail?.trim() || quote.issuerContactEmail?.trim() || '';
}

export function quotationBelongsToUser(quote: Quotation, user?: QuoteUserRef): boolean {
  if (!user?.email) return true;

  const ownerEmail = resolveQuoteOwnerEmail(quote);
  if (ownerEmail) {
    return ownerEmail.toLowerCase() === user.email.toLowerCase();
  }

  if (user.name && quote.salesperson?.trim() === user.name.trim()) {
    return true;
  }

  return false;
}

export function filterQuotationsByUser(quotations: Quotation[], user?: QuoteUserRef): Quotation[] {
  if (!user?.email) return quotations;
  return quotations.filter(quote => quotationBelongsToUser(quote, user));
}

export function ensureQuoteOwnership(
  quote: Quotation,
  user?: QuoteUserRef,
  options?: { force?: boolean },
): Quotation {
  if (!user?.email) return quote;
  if (!options?.force && quote.createdByEmail?.trim()) return quote;

  return {
    ...quote,
    createdByEmail: user.email,
  };
}
