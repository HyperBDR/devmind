import type { Quotation } from '../types';

export interface CustomerHistoryRecord {
  clientCompany: string;
  contactPerson: string;
  email: string;
  createdAt?: string;
}

type CustomerHistorySource = Pick<Quotation, 'clientCompany' | 'contactPerson' | 'email' | 'createdAt'>;

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

function uniqueBy<T>(items: T[], getKey: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter(item => {
    const key = normalize(getKey(item));
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function buildCustomerHistory(quotations: CustomerHistorySource[]): CustomerHistoryRecord[] {
  return quotations
    .map(quote => ({
      clientCompany: quote.clientCompany.trim(),
      contactPerson: quote.contactPerson.trim(),
      email: quote.email.trim(),
      createdAt: quote.createdAt,
    }))
    .filter(record => record.clientCompany || record.contactPerson || record.email)
    .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''));
}

export function getCompanyOptions(history: CustomerHistoryRecord[]): CustomerHistoryRecord[] {
  return uniqueBy(history.filter(record => record.clientCompany), record => record.clientCompany);
}

export function getCompanyOptionLabel(history: CustomerHistoryRecord[], clientCompany: string): string | undefined {
  const contacts = getContactOptions(history, clientCompany)
  if (contacts.length <= 1) return undefined
  return `${contacts.length} 位历史联系人`
}

export function getContactOptions(history: CustomerHistoryRecord[], clientCompany = ''): CustomerHistoryRecord[] {
  const scopedHistory = clientCompany.trim()
    ? history.filter(record => normalize(record.clientCompany) === normalize(clientCompany))
    : history;
  return uniqueBy(scopedHistory.filter(record => record.contactPerson), record => `${record.contactPerson}|${record.email}`);
}

export function getEmailOptions(history: CustomerHistoryRecord[], clientCompany = ''): CustomerHistoryRecord[] {
  const scopedHistory = clientCompany.trim()
    ? history.filter(record => normalize(record.clientCompany) === normalize(clientCompany))
    : history;
  return uniqueBy(scopedHistory.filter(record => record.email), record => record.email);
}

export function findCustomerByCompany(
  history: CustomerHistoryRecord[],
  clientCompany: string
): CustomerHistoryRecord | undefined {
  const target = normalize(clientCompany);
  if (!target) return undefined;
  return history.find(record => normalize(record.clientCompany) === target);
}

export function findCustomerByContact(
  history: CustomerHistoryRecord[],
  contactPerson: string,
  clientCompany = ''
): CustomerHistoryRecord | undefined {
  const target = normalize(contactPerson);
  if (!target) return undefined;
  const scopedMatch = clientCompany.trim()
    ? history.find(record => normalize(record.clientCompany) === normalize(clientCompany) && normalize(record.contactPerson) === target)
    : undefined;
  return scopedMatch || history.find(record => normalize(record.contactPerson) === target);
}

export function findCustomerByEmail(
  history: CustomerHistoryRecord[],
  email: string
): CustomerHistoryRecord | undefined {
  const target = normalize(email);
  if (!target) return undefined;
  return history.find(record => normalize(record.email) === target);
}

export interface BillingHistoryRecord {
  billingCompany: string;
  billingContact: string;
  billingEmail: string;
  createdAt?: string;
}

type BillingHistorySource = Pick<
  Quotation,
  | 'billingCompany'
  | 'billingContact'
  | 'billingEmail'
  | 'clientCompany'
  | 'contactPerson'
  | 'email'
  | 'createdAt'
>;

function toBillingRecord(quote: BillingHistorySource): BillingHistoryRecord {
  return {
    billingCompany: (quote.billingCompany || quote.clientCompany).trim(),
    billingContact: (quote.billingContact || quote.contactPerson).trim(),
    billingEmail: (quote.billingEmail || quote.email).trim(),
    createdAt: quote.createdAt,
  };
}

export function buildBillingHistory(quotations: BillingHistorySource[]): BillingHistoryRecord[] {
  const billingRecords = quotations.map(toBillingRecord);
  const customerRecords = buildCustomerHistory(quotations).map(record => ({
    billingCompany: record.clientCompany,
    billingContact: record.contactPerson,
    billingEmail: record.email,
    createdAt: record.createdAt,
  }));

  return uniqueBy(
    [...billingRecords, ...customerRecords].filter(
      record => record.billingCompany || record.billingContact || record.billingEmail,
    ),
    record => `${record.billingCompany}|${record.billingContact}|${record.billingEmail}`,
  ).sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''));
}

export function getBillingCompanyOptions(history: BillingHistoryRecord[]): BillingHistoryRecord[] {
  return uniqueBy(history.filter(record => record.billingCompany), record => record.billingCompany);
}

export function getBillingCompanyOptionLabel(
  history: BillingHistoryRecord[],
  billingCompany: string,
): string | undefined {
  const contacts = getBillingContactOptions(history, billingCompany)
  if (contacts.length <= 1) return undefined
  return `${contacts.length} 位历史联系人`
}

export function getBillingContactOptions(
  history: BillingHistoryRecord[],
  billingCompany = '',
): BillingHistoryRecord[] {
  const scopedHistory = billingCompany.trim()
    ? history.filter(record => normalize(record.billingCompany) === normalize(billingCompany))
    : history;
  return uniqueBy(
    scopedHistory.filter(record => record.billingContact),
    record => `${record.billingContact}|${record.billingEmail}`,
  );
}

export function getBillingEmailOptions(
  history: BillingHistoryRecord[],
  billingCompany = '',
): BillingHistoryRecord[] {
  const scopedHistory = billingCompany.trim()
    ? history.filter(record => normalize(record.billingCompany) === normalize(billingCompany))
    : history;
  return uniqueBy(scopedHistory.filter(record => record.billingEmail), record => record.billingEmail);
}

export function findBillingByCompany(
  history: BillingHistoryRecord[],
  billingCompany: string,
): BillingHistoryRecord | undefined {
  const target = normalize(billingCompany);
  if (!target) return undefined;
  return history.find(record => normalize(record.billingCompany) === target);
}

export function findBillingByContact(
  history: BillingHistoryRecord[],
  billingContact: string,
  billingCompany = '',
): BillingHistoryRecord | undefined {
  const target = normalize(billingContact);
  if (!target) return undefined;
  const scopedMatch = billingCompany.trim()
    ? history.find(
        record =>
          normalize(record.billingCompany) === normalize(billingCompany) &&
          normalize(record.billingContact) === target,
      )
    : undefined;
  return scopedMatch || history.find(record => normalize(record.billingContact) === target);
}

export function findBillingByEmail(
  history: BillingHistoryRecord[],
  billingEmail: string,
): BillingHistoryRecord | undefined {
  const target = normalize(billingEmail);
  if (!target) return undefined;
  return history.find(record => normalize(record.billingEmail) === target);
}
