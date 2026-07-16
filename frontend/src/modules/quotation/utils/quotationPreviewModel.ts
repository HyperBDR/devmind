import type { Quotation, QuotationLineItem } from '../types';
import { resolveTaxLabel } from './taxLabels';

export const DEFAULT_ISSUER_COMPANY_NAME = 'OnePro Cloud Limited';

export const DEFAULT_REMARKS_DISCLAIMER = `This quotation is based on the information currently provided and collected during the pre-sales stage. Any changes to scope, environment, requirements, or deployment complexity may result in adjustments to pricing and delivery timelines.

The Professional Services scope covers OnePro product-level installation, configuration, and deployment activities only. The customer is responsible for ensuring the target environment is fully prepared prior to implementation, including but not limited to network connectivity, firewall and security policy configuration, required bandwidth, system accessibility, permissions, credentials, and environment readiness.

Any work outside the defined product deployment scope, including infrastructure rectification, network troubleshooting, third-party integration, OS/application-level remediation, or environment preparation, is not included unless otherwise stated.

Please note that the quoted price does not include any cloud resource consumption costs. All prices quoted are exclusive of VAT and any applicable taxes.`;

export interface PreviewUser {
  name: string;
  title: string;
  email: string;
  role?: string;
}

export interface PreviewLineItem extends QuotationLineItem {
  lineNo: number;
}

export interface QuotationPreviewModel {
  quoteNo: string;
  issuerCompanyName: string;
  quoteDate: string;
  validTill: string;
  customerCompany: string;
  contactPerson: string;
  email: string;
  billingCompany: string;
  billingContact: string;
  billingEmail: string;
  projectName: string;
  paymentTerms: string;
  currency: Quotation['currency'];
  currencySymbol: string;
  softwareItems: PreviewLineItem[];
  othersItems: PreviewLineItem[];
  softwareRows: PreviewLineItem[];
  othersRows: PreviewLineItem[];
  softwareSubtotal: number;
  othersSubtotal: number;
  subtotalBeforeVat: number;
  taxLabel: string;
  vatRate: number;
  vatAmount: number;
  grandTotal: number;
  remarksDisclaimer: string;
  issuerSignature: string;
  signer: PreviewUser;
}

interface BuildOptions {
  currentUser?: PreviewUser;
  today?: Date;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function formatDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function getCurrencySymbol(currency: Quotation['currency']): string {
  if (currency === 'USD') return '$';
  if (currency === 'EUR') return '€';
  return '¥';
}

function withLineNumbers(items: QuotationLineItem[]): PreviewLineItem[] {
  return items.map((item, index) => ({
    ...item,
    lineNo: index + 1,
  }));
}

function blankLine(lineNo: number, type: QuotationLineItem['type']): PreviewLineItem {
  return {
    id: `blank-${type}-${lineNo}`,
    type,
    itemId: '',
    name: '',
    description: '',
    listPrice: 0,
    discountPercent: 0,
    qty: 0,
    netUnitPrice: 0,
    extendedPrice: 0,
    lineNo,
  };
}

function fitTemplateRows(items: PreviewLineItem[], count: number, type: QuotationLineItem['type']): PreviewLineItem[] {
  return Array.from(
    { length: Math.max(count, items.length) },
    (_, index) => items[index] || blankLine(index + 1, type),
  );
}

export function resolveIssuerSigner(quote: Quotation, currentUser?: PreviewUser): PreviewUser {
  return {
    name: quote.issuerContactName?.trim() || currentUser?.name || quote.salesperson?.trim() || 'Alice Chen',
    title: quote.issuerContactTitle?.trim() || currentUser?.title || 'Sales Manager',
    email: quote.issuerContactEmail?.trim() || currentUser?.email || 'sales@oneprocloud.com',
    role: currentUser?.role,
  };
}

export function buildQuotationPreviewModel(quote: Quotation, options: BuildOptions = {}): QuotationPreviewModel {
  const today = options.today || new Date();
  const quoteDate = quote.quoteDate || formatDate(today);
  const validTill = quote.expireDate || formatDate(new Date(today.getTime() + 30 * DAY_MS));
  const signer = resolveIssuerSigner(quote, options.currentUser);

  const softwareItems = withLineNumbers(quote.items.filter(item => item.type === 'Software'));
  const othersItems = withLineNumbers(quote.items.filter(item => item.type !== 'Software'));

  return {
    quoteNo: quote.quoteNo,
    issuerCompanyName: quote.issuerCompanyName ?? DEFAULT_ISSUER_COMPANY_NAME,
    quoteDate,
    validTill,
    customerCompany: quote.clientCompany,
    contactPerson: quote.contactPerson,
    email: quote.email,
    billingCompany: quote.billingCompany || quote.clientCompany,
    billingContact: quote.billingContact || quote.contactPerson,
    billingEmail: quote.billingEmail || quote.email,
    projectName: quote.projectName,
    paymentTerms: quote.paymentTerms,
    currency: quote.currency,
    currencySymbol: getCurrencySymbol(quote.currency),
    softwareItems,
    othersItems,
    softwareRows: fitTemplateRows(softwareItems, 3, 'Software'),
    othersRows: fitTemplateRows(othersItems, 5, 'Other'),
    softwareSubtotal: quote.softwareSubtotal,
    othersSubtotal: quote.othersSubtotal,
    subtotalBeforeVat: quote.subtotalBeforeVat ?? quote.softwareSubtotal + quote.othersSubtotal,
    taxLabel: resolveTaxLabel(quote.taxLabel),
    vatRate: quote.vatRate ?? 0,
    vatAmount: quote.vatAmount ?? 0,
    grandTotal: quote.grandTotal,
    remarksDisclaimer: quote.remarksDisclaimer ?? '',
    issuerSignature: quote.issuerSignature ?? '',
    signer,
  };
}
