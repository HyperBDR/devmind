/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type ItemType = 'Software' | 'Service' | 'Other';

export type QuoteStatus = 'Draft' | 'Generated' | 'Uploaded' | 'Sent' | 'Accepted' | 'Rejected' | 'Expired' | 'Cancelled';
export type QuoteProductLine = string;
export type PaymentTermOption = 'CIA' | 'NET 30' | 'NET 45' | 'NET 60' | 'Mixed' | 'Others';

export interface ProductLineOption {
  value: QuoteProductLine;
  label: string;
}

export interface QuotationLineItem {
  id: string;
  type: ItemType;
  itemId: string; // Legacy catalog reference. New quotes use manual line entry.
  name: string;
  description?: string;
  listPrice: number;
  discountPercent: number; // 0 - 100
  qty: number;
  netUnitPrice: number; // listPrice * (1 - discountPercent / 100)
  extendedPrice: number; // netUnitPrice * qty
}

export interface QuoteVersion {
  id: string;
  versionNo: string;
  updateTime: string;
  operator: string;
  status: QuoteStatus;
  grandTotal: number;
  notes: string;
  items: QuotationLineItem[];
  projectName: string;
  clientCompany: string;
  contactPerson: string;
  email: string;
  productLine?: QuoteProductLine;
  billingCompany?: string;
  billingContact?: string;
  billingEmail?: string;
  region: string;
  industry: string;
  salesperson: string;
  createdByEmail?: string;
  currency: 'CNY' | 'USD' | 'EUR';
  paymentTermOption?: PaymentTermOption;
  paymentTerms: string;
  quoteDate?: string;
  expireDate?: string;
  remarksDisclaimer?: string;
  issuerCompanyName?: string;
  issuerContactName?: string;
  issuerContactEmail?: string;
  issuerContactTitle?: string;
  issuerSignature?: string;
  softwareSubtotal: number;
  othersSubtotal: number;
  subtotalBeforeVat: number;
  taxLabel?: string;
  vatRate: number;
  vatAmount: number;
  excelGeneratedAt?: string;
  excelFileName?: string;
}

export interface Quotation {
  id: string;
  quoteNo: string;
  projectName: string;
  clientCompany: string;
  contactPerson: string;
  email: string;
  productLine?: QuoteProductLine;
  billingCompany?: string;
  billingContact?: string;
  billingEmail?: string;
  region: string;
  industry: string;
  salesperson: string;
  createdByEmail?: string;
  currency: 'CNY' | 'USD' | 'EUR';
  paymentTermOption?: PaymentTermOption;
  paymentTerms: string;
  quoteDate?: string;
  expireDate?: string;
  remarksDisclaimer?: string;
  issuerCompanyName?: string;
  issuerContactName?: string;
  issuerContactEmail?: string;
  issuerContactTitle?: string;
  issuerSignature?: string;
  status: QuoteStatus;
  items: QuotationLineItem[];
  softwareSubtotal: number;
  othersSubtotal: number;
  subtotalBeforeVat: number;
  taxLabel?: string;
  vatRate: number;
  vatAmount: number;
  grandTotal: number;
  createdAt: string;
  updatedAt?: string;

  // Excel generation metadata
  excelGeneratedAt?: string;
  excelFileName?: string;

  // Feishu simulation data
  feishuFileToken?: string;
  feishuUrl?: string;
  feishuPath?: string;
  feishuUploadedAt?: string;
  feishuDocumentId?: string;
  feishuExcelFileToken?: string;
  feishuExcelUrl?: string;
  feishuExcelDocumentId?: string;
  feishuExcelPath?: string;
  feishuExcelUploadedAt?: string;
  feishuPdfFileToken?: string;
  feishuPdfUrl?: string;
  feishuPdfDocumentId?: string;
  feishuPdfPath?: string;
  feishuPdfUploadedAt?: string;

  // Version history
  versions?: QuoteVersion[];
}

export interface Product {
  id: string;
  name: string;
  code: string;
  listPrice: number;
  currency?: Quotation['currency'];
  category: string;
  description: string;
  pricingNote?: string;
  sourceSheet?: string;
  sourceRow?: number;
}

export interface Service {
  id: string;
  name: string;
  code: string;
  listPrice: number;
  currency?: Quotation['currency'];
  unit: string; // e.g., 人天, 项, 月
  description: string;
  quantityRange?: string;
  quantityMin?: number;
  quantityMax?: number;
  pricingNote?: string;
  sourceSheet?: string;
  sourceRow?: number;
}

export interface DiscountOption {
  id: string;
  name: string;
  percent: number; // 0 - 100
  condition?: string;
  threshold?: number;
  sourceSheet?: string;
  sourceRow?: number;
}
