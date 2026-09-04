/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type ItemType = 'Software' | 'Service' | 'Other';
export type LineItemCurrency = 'CNY' | 'USD' | 'EUR' | 'MYR' | 'HKD';

export type QuoteStatus = 'Draft' | 'Generated' | 'Uploaded' | 'Sent' | 'Accepted' | 'Rejected' | 'Expired' | 'Cancelled';
export type QuoteProductLine = string;
export type PaymentTermOption = 'CIA' | 'NET 30' | 'NET 45' | 'NET 60' | 'Mixed' | 'Others';
export type TaxCalculation = 'add' | 'subtract';

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
  currency?: LineItemCurrency;
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
  productLineName?: string;
  billingCompany?: string;
  billingContact?: string;
  billingEmail?: string;
  region: string;
  industry: string;
  salesperson: string;
  createdByEmail?: string;
  currency: string;
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
  taxCalculation?: TaxCalculation;
  additionalGrandTotalCurrency?: string;
  additionalGrandTotalLabel?: string;
  additionalGrandTotalAmount?: number;
  excelGeneratedAt?: string;
  excelFileName?: string;
}

export interface Quotation {
  id: string;
  quoteNo: string;
  quoteNoMode?: 'auto' | 'custom';
  sourceType?: 'manual' | 'document_import';
  sourceDocumentType?: 'excel' | 'pdf';
  sourceDocument?: {
    id: string;
    docType: 'excel' | 'pdf';
    fileName: string;
    versionNo: number;
  };
  availableVersions?: Array<{
    versionNo: number;
    status: string;
    createdAt: string;
  }>;
  versionCurrent?: number;
  projectName: string;
  clientCompany: string;
  contactPerson: string;
  email: string;
  productLine?: QuoteProductLine;
  productLineName?: string;
  billingCompany?: string;
  billingContact?: string;
  billingEmail?: string;
  region: string;
  industry: string;
  salesperson: string;
  createdByEmail?: string;
  currency: string;
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
  itemCount?: number;
  softwareSubtotal: number;
  othersSubtotal: number;
  subtotalBeforeVat: number;
  taxLabel?: string;
  vatRate: number;
  vatAmount: number;
  taxCalculation?: TaxCalculation;
  grandTotal: number;
  additionalGrandTotalCurrency?: string;
  additionalGrandTotalLabel?: string;
  additionalGrandTotalAmount?: number;
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
  prices?: Partial<Record<LineItemCurrency, number>>;
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
  prices?: Partial<Record<LineItemCurrency, number>>;
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
