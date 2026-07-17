/**
 * Build Excel quotation that mirrors QuotationPreview layout 1:1.
 */

import ExcelJS from 'exceljs';

import type { Quotation } from '../types';
import { buildQuotationExportFileName } from './quotationFileName';
import {
  buildQuotationPreviewModel,
  type PreviewLineItem,
  type PreviewUser,
  type QuotationPreviewModel,
} from './quotationPreviewModel';

const LOGO_URL = new URL('../assets/onepro-logo.png', import.meta.url).href;

const COLS = 7;
const FONT = 'Calibri';
const COLOR_TEXT = 'FF0F172A';
const COLOR_MUTED = 'FF334155';
const COLOR_HEADER = 'FFE2E8F0';
const COLOR_SOFT = 'FFF8FAFC';
const COLOR_LINK = 'FF2563EB';

const THIN: Partial<ExcelJS.Border> = {
  style: 'thin',
  color: { argb: 'FF000000' },
};
const BOX: Partial<ExcelJS.Border> = {
  style: 'thin',
  color: { argb: 'FF000000' },
};
const UNDERLINE: Partial<ExcelJS.Border> = {
  style: 'thin',
  color: { argb: 'FF000000' },
};
const GRID: Partial<ExcelJS.Border> = {
  style: 'thin',
  color: { argb: 'FF94A3B8' },
};

function money(value: number): string {
  if (!value) return '';
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
}

function percent(value: number): string {
  return value ? `${value}%` : '0%';
}

function rowHasContent(item: PreviewLineItem): boolean {
  return Boolean(item.name || item.description);
}

function rowDescription(item: PreviewLineItem): string {
  return item.description || item.name || '';
}

function lineItemRowHeight(description: string): number {
  const visualLines = Math.max(1, Math.ceil(description.length / 38));
  return Math.max(24, visualLines * 15);
}

function parseImageDataUrl(
  dataUrl: string,
): { base64: string; extension: 'png' | 'jpeg' } | null {
  const match = dataUrl.match(/^data:image\/(png|jpe?g);base64,([\s\S]+)$/i);
  if (!match) return null;
  return {
    extension: match[1].toLowerCase().startsWith('j') ? 'jpeg' : 'png',
    base64: match[2],
  };
}

async function toDataUrl(url: string): Promise<string | null> {
  if (url.startsWith('data:')) return url;
  if (typeof fetch === 'undefined') return null;
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const blob = await response.blob();
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || '') || null);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

function styleFont(
  cell: ExcelJS.Cell,
  opts: {
    size?: number;
    bold?: boolean;
    underline?: boolean;
    color?: string;
    mono?: boolean;
  } = {},
) {
  cell.font = {
    name: opts.mono ? 'Consolas' : FONT,
    size: opts.size ?? 11,
    bold: opts.bold ?? false,
    underline: opts.underline ?? false,
    color: { argb: opts.color ?? COLOR_TEXT },
  };
}

function align(
  cell: ExcelJS.Cell,
  horizontal: ExcelJS.Alignment['horizontal'],
  wrap = true,
) {
  cell.alignment = {
    vertical: 'middle',
    horizontal,
    wrapText: wrap,
  };
}

function fillSolid(cell: ExcelJS.Cell, argb: string) {
  cell.fill = {
    type: 'pattern',
    pattern: 'solid',
    fgColor: { argb },
  };
}

function borderAll(
  cell: ExcelJS.Cell,
  border: Partial<ExcelJS.Border> = THIN,
) {
  cell.border = {
    top: { ...border },
    left: { ...border },
    bottom: { ...border },
    right: { ...border },
  };
}

/**
 * Paint borders on every cell in a row span, then keep them after merge.
 * Excel often drops borders on secondary merged cells if only the master
 * cell is styled.
 */
function frameRowSpan(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
  border: Partial<ExcelJS.Border> = BOX,
) {
  for (let col = startCol; col <= endCol; col += 1) {
    borderAll(sheet.getCell(row, col), border);
  }
}

function fillRowSpan(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
  argb: string,
) {
  for (let col = startCol; col <= endCol; col += 1) {
    fillSolid(sheet.getCell(row, col), argb);
  }
}

function setSpannedText(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
  value: string,
  style: (cell: ExcelJS.Cell) => void,
  opts?: {
    border?: Partial<ExcelJS.Border>;
    fill?: string;
    merge?: boolean;
  },
) {
  const cell = sheet.getCell(row, startCol);
  cell.value = value;
  style(cell);
  if (opts?.fill) {
    fillRowSpan(sheet, row, startCol, endCol, opts.fill);
  }
  if (opts?.border) {
    frameRowSpan(sheet, row, startCol, endCol, opts.border);
  }
  if (opts?.merge !== false && endCol > startCol) {
    sheet.mergeCells(row, startCol, row, endCol);
    // Re-apply frame after merge so Excel keeps outer edges.
    if (opts?.border) {
      frameRowSpan(sheet, row, startCol, endCol, opts.border);
    }
    if (opts?.fill) {
      fillRowSpan(sheet, row, startCol, endCol, opts.fill);
    }
  }
}

function setSpannedRichLabel(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
  label: string,
  value: string,
  border: Partial<ExcelJS.Border> = BOX,
) {
  const cell = sheet.getCell(row, startCol);
  cell.value = {
    richText: [
      {
        text: label,
        font: {
          name: FONT,
          size: 11,
          bold: true,
          color: { argb: COLOR_TEXT },
        },
      },
      {
        text: value,
        font: {
          name: FONT,
          size: 11,
          bold: false,
          color: { argb: COLOR_TEXT },
        },
      },
    ],
  };
  align(cell, 'left');
  frameRowSpan(sheet, row, startCol, endCol, border);
  if (endCol > startCol) {
    sheet.mergeCells(row, startCol, row, endCol);
    frameRowSpan(sheet, row, startCol, endCol, border);
  }
}

function merge(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
) {
  if (endCol > startCol) {
    sheet.mergeCells(row, startCol, row, endCol);
  }
}

function setMerged(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
  value: string,
  style: (cell: ExcelJS.Cell) => void,
) {
  setSpannedText(sheet, row, startCol, endCol, value, style, {
    merge: true,
  });
}

function setRichLabelValue(
  sheet: ExcelJS.Worksheet,
  row: number,
  startCol: number,
  endCol: number,
  label: string,
  value: string,
) {
  setSpannedRichLabel(sheet, row, startCol, endCol, label, value, BOX);
}

class PreviewExcelBuilder {
  private workbook: ExcelJS.Workbook;
  private sheet: ExcelJS.Worksheet;
  private row = 1;

  constructor() {
    this.workbook = new ExcelJS.Workbook();
    this.workbook.creator = 'DevMind Quote Desk';
    this.sheet = this.workbook.addWorksheet('Quotation', {
      views: [{ showGridLines: false }],
      pageSetup: {
        paperSize: 9,
        orientation: 'portrait',
        fitToPage: true,
        fitToWidth: 1,
        fitToHeight: 0,
        horizontalCentered: true,
      },
    });
    this.sheet.columns = [
      { width: 14 },
      { width: 28 },
      { width: 8 },
      { width: 14 },
      { width: 12 },
      { width: 18 },
      { width: 16 },
    ];
  }

  private nextRow(height?: number): number {
    const current = this.row;
    if (height != null) {
      this.sheet.getRow(current).height = height;
    }
    this.row += 1;
    return current;
  }

  private spacer(height: number) {
    const r = this.nextRow(height);
    merge(this.sheet, r, 1, COLS);
  }

  async addLogo() {
    const dataUrl = await toDataUrl(LOGO_URL);
    if (!dataUrl) return;
    const parsed = parseImageDataUrl(dataUrl);
    if (!parsed) return;
    const imageId = this.workbook.addImage({
      base64: parsed.base64,
      extension: parsed.extension,
    });
    this.sheet.addImage(imageId, {
      tl: { col: 0.15, row: 0.2 },
      ext: { width: 166, height: 52 },
    });
  }

  addTitle(model: QuotationPreviewModel) {
    this.spacer(56);
    const companyRow = this.nextRow(24);
    setMerged(this.sheet, companyRow, 1, COLS, model.issuerCompanyName, (cell) => {
      styleFont(cell, { size: 18, bold: true });
      align(cell, 'center');
    });

    const titleRow = this.nextRow(28);
    setMerged(this.sheet, titleRow, 1, COLS, 'Quotation', (cell) => {
      styleFont(cell, { size: 22, bold: true, underline: true });
      align(cell, 'center');
    });
    this.spacer(16);
  }

  addMeta(model: QuotationPreviewModel) {
    const dateRow = this.nextRow(18);
    setMerged(this.sheet, dateRow, 6, 6, 'Date:', (cell) => {
      styleFont(cell, { size: 11, bold: true });
      align(cell, 'right', false);
    });
    const dateValue = this.sheet.getCell(dateRow, 7);
    dateValue.value = model.quoteDate;
    styleFont(dateValue, { size: 11, mono: true });
    align(dateValue, 'right', false);
    dateValue.border = { bottom: { ...UNDERLINE } };

    const shipHeaderRow = this.nextRow(18);
    setSpannedText(
      this.sheet,
      shipHeaderRow,
      1,
      2,
      'Ship to',
      (cell) => {
        styleFont(cell, { size: 11, bold: true });
        align(cell, 'center');
      },
      { border: BOX, fill: COLOR_HEADER },
    );
    setMerged(this.sheet, shipHeaderRow, 6, 6, 'Quote No.:', (cell) => {
      styleFont(cell, { size: 11, bold: true });
      align(cell, 'right', false);
    });
    const quoteNo = this.sheet.getCell(shipHeaderRow, 7);
    quoteNo.value = model.quoteNo;
    styleFont(quoteNo, { size: 11, mono: true });
    align(quoteNo, 'right', false);
    quoteNo.border = { bottom: { ...UNDERLINE } };

    const shipCompanyRow = this.nextRow(20);
    setRichLabelValue(
      this.sheet,
      shipCompanyRow,
      1,
      2,
      'Company : ',
      model.customerCompany || '',
    );
    setMerged(this.sheet, shipCompanyRow, 6, 6, 'Quote Valid Till:', (cell) => {
      styleFont(cell, { size: 11, bold: true });
      align(cell, 'right', false);
    });
    const validTill = this.sheet.getCell(shipCompanyRow, 7);
    validTill.value = model.validTill;
    styleFont(validTill, { size: 11, mono: true });
    align(validTill, 'right', false);
    validTill.border = { bottom: { ...UNDERLINE } };

    const shipNameRow = this.nextRow(20);
    setRichLabelValue(
      this.sheet,
      shipNameRow,
      1,
      2,
      'Name : ',
      model.contactPerson || '',
    );

    const shipEmailRow = this.nextRow(20);
    setRichLabelValue(
      this.sheet,
      shipEmailRow,
      1,
      2,
      'Email : ',
      model.email || '',
    );

    this.spacer(10);

    const billHeaderRow = this.nextRow(18);
    setSpannedText(
      this.sheet,
      billHeaderRow,
      1,
      2,
      'Bill to:',
      (cell) => {
        styleFont(cell, { size: 11, bold: true });
        align(cell, 'center');
      },
      { border: BOX, fill: COLOR_HEADER },
    );

    const billCompanyRow = this.nextRow(20);
    setRichLabelValue(
      this.sheet,
      billCompanyRow,
      1,
      2,
      'Company : ',
      model.billingCompany || '',
    );

    const billNameRow = this.nextRow(20);
    setRichLabelValue(
      this.sheet,
      billNameRow,
      1,
      2,
      'Name : ',
      model.billingContact || '',
    );

    const billEmailRow = this.nextRow(20);
    setRichLabelValue(
      this.sheet,
      billEmailRow,
      1,
      2,
      'Email : ',
      model.billingEmail || '',
    );

    this.spacer(12);
  }

  addProjectMeta(model: QuotationPreviewModel) {
    const headerRow = this.nextRow(20);
    const headers: Array<{ start: number; end: number; text: string }> = [
      { start: 1, end: 1, text: 'Contact Person' },
      { start: 2, end: 2, text: 'Email' },
      { start: 3, end: 5, text: 'Project' },
      { start: 6, end: 6, text: 'Payment Terms' },
      { start: 7, end: 7, text: 'Currency' },
    ];
    headers.forEach(({ start, end, text }) => {
      setSpannedText(
        this.sheet,
        headerRow,
        start,
        end,
        text,
        (cell) => {
          styleFont(cell, { size: 12, bold: true });
          align(cell, 'left', false);
        },
        { border: GRID, fill: COLOR_HEADER },
      );
    });

    const valueRow = this.nextRow(22);
    const values: Array<{
      start: number;
      end: number;
      text: string;
      mono?: boolean;
    }> = [
      { start: 1, end: 1, text: model.signer.name },
      { start: 2, end: 2, text: model.signer.email },
      { start: 3, end: 5, text: model.projectName || '-' },
      { start: 6, end: 6, text: model.paymentTerms || '-' },
      { start: 7, end: 7, text: model.currency, mono: true },
    ];
    values.forEach(({ start, end, text, mono }) => {
      setSpannedText(
        this.sheet,
        valueRow,
        start,
        end,
        text,
        (cell) => {
          styleFont(cell, { size: 11, mono });
          align(cell, 'left');
        },
        { border: GRID },
      );
    });

    this.spacer(16);
  }

  private addLineSection(
    title: string,
    rows: PreviewLineItem[],
    subtotalLabel: string,
    subtotal: number,
  ) {
    const titleRow = this.nextRow(20);
    setSpannedText(
      this.sheet,
      titleRow,
      1,
      COLS,
      title,
      (cell) => {
        styleFont(cell, { size: 12, bold: true });
        align(cell, 'left', false);
      },
      { border: GRID, fill: COLOR_HEADER },
    );

    const headerRow = this.nextRow(18);
    const colHeaders = [
      'Item',
      'Description',
      'Qty',
      'List Price',
      'Discount (%)',
      'Discounted Price',
      'Extended Price',
    ];
    colHeaders.forEach((text, index) => {
      const cell = this.sheet.getCell(headerRow, index + 1);
      cell.value = text;
      styleFont(cell, { size: 11, bold: true });
      align(cell, 'center', false);
      fillSolid(cell, COLOR_SOFT);
      borderAll(cell, GRID);
    });

    rows.forEach((item) => {
      const r = this.nextRow(lineItemRowHeight(rowDescription(item)));
      const hasContent = rowHasContent(item);
      const values = [
        hasContent ? String(item.lineNo) : '',
        rowDescription(item),
        hasContent ? String(item.qty) : '',
        hasContent ? money(item.listPrice) : '',
        hasContent ? percent(item.discountPercent) : '',
        hasContent ? money(item.netUnitPrice) : '',
        hasContent ? money(item.extendedPrice) : '',
      ];
      values.forEach((value, index) => {
        const cell = this.sheet.getCell(r, index + 1);
        cell.value = value;
        const isMoney = index === 3 || index === 5 || index === 6;
        const isCenter = index === 0 || index === 2 || index === 4;
        styleFont(cell, {
          size: 11,
          mono: isMoney || isCenter,
        });
        align(cell, isMoney ? 'right' : isCenter ? 'center' : 'left');
        borderAll(cell, GRID);
      });
    });

    const subtotalRow = this.nextRow(20);
    setSpannedText(
      this.sheet,
      subtotalRow,
      5,
      6,
      subtotalLabel,
      (cell) => {
        styleFont(cell, { size: 11, bold: true });
        align(cell, 'right', false);
      },
      { border: GRID },
    );
    const amount = this.sheet.getCell(subtotalRow, 7);
    amount.value = money(subtotal);
    styleFont(amount, { size: 11, bold: true, mono: true });
    align(amount, 'right', false);
    borderAll(amount, GRID);

    this.spacer(16);
  }

  addLineItems(model: QuotationPreviewModel) {
    this.addLineSection(
      'Software',
      model.softwareRows,
      'Software subscription subtotal:',
      model.softwareSubtotal,
    );
    this.addLineSection(
      'Others',
      model.othersRows,
      'Others Subtotal:',
      model.othersSubtotal,
    );
  }

  addTotals(model: QuotationPreviewModel) {
    const rows: Array<{ label: string; value: number }> = [
      {
        label: `Subtotal before ${model.taxLabel}:`,
        value: model.subtotalBeforeVat,
      },
      {
        label: `${model.taxLabel} Amount (${model.vatRate}%):`,
        value: model.vatAmount,
      },
      {
        label: 'Grand Total:',
        value: model.grandTotal,
      },
    ];

    rows.forEach(({ label, value }) => {
      const r = this.nextRow(20);
      setSpannedText(
        this.sheet,
        r,
        5,
        6,
        label,
        (cell) => {
          styleFont(cell, { size: 11, bold: true });
          align(cell, 'right', false);
        },
        { border: GRID },
      );
      const amount = this.sheet.getCell(r, 7);
      amount.value = money(value);
      styleFont(amount, { size: 11, bold: true, mono: true });
      align(amount, 'right', false);
      borderAll(amount, GRID);
    });

    this.spacer(10);
  }

  addNotes(model: QuotationPreviewModel) {
    const labelRow = this.nextRow(18);
    setMerged(
      this.sheet,
      labelRow,
      1,
      COLS,
      'Additional Notes & Disclaimers:',
      (cell) => {
        styleFont(cell, { size: 11, bold: true });
        align(cell, 'left', false);
      },
    );

    const notesRow = this.nextRow(72);
    setSpannedText(
      this.sheet,
      notesRow,
      1,
      COLS,
      model.remarksDisclaimer || '',
      (cell) => {
        styleFont(cell, { size: 9, color: COLOR_MUTED });
        align(cell, 'left');
      },
      { border: GRID, fill: COLOR_SOFT },
    );

    const acceptRow = this.nextRow(28);
    setMerged(
      this.sheet,
      acceptRow,
      1,
      COLS,
      'To indicate Customer acceptance of this quotation, please sign below and return one copy of this quotation to OnePro Cloud.',
      (cell) => {
        styleFont(cell, { size: 11 });
        align(cell, 'left');
      },
    );

    this.spacer(20);
  }

  async addSignatures(model: QuotationPreviewModel) {
    const companyRow = this.nextRow(18);
    setMerged(
      this.sheet,
      companyRow,
      5,
      COLS,
      model.issuerCompanyName,
      (cell) => {
        styleFont(cell, { size: 11, bold: true });
        align(cell, 'left', false);
      },
    );

    const signRow = this.nextRow(36);
    merge(this.sheet, signRow, 1, 3);
    merge(this.sheet, signRow, 5, COLS);
    const leftLine = this.sheet.getCell(signRow, 1);
    leftLine.border = { bottom: UNDERLINE };
    const rightLine = this.sheet.getCell(signRow, 5);
    rightLine.border = { bottom: UNDERLINE };

    if (model.issuerSignature) {
      const parsed = parseImageDataUrl(model.issuerSignature);
      if (parsed) {
        const imageId = this.workbook.addImage({
          base64: parsed.base64,
          extension: parsed.extension,
        });
        this.sheet.addImage(imageId, {
          tl: { col: 4.05, row: signRow - 1.15 },
          ext: { width: 180, height: 32 },
        });
      }
    }

    const nameRow = this.nextRow(18);
    setMerged(this.sheet, nameRow, 1, 3, 'Name :', (cell) => {
      styleFont(cell, { size: 11 });
      align(cell, 'left', false);
    });
    setMerged(
      this.sheet,
      nameRow,
      5,
      COLS,
      `Name : ${model.signer.name}`,
      (cell) => {
        styleFont(cell, { size: 11 });
        align(cell, 'left', false);
      },
    );

    const titleRow = this.nextRow(18);
    setMerged(this.sheet, titleRow, 1, 3, 'Title :', (cell) => {
      styleFont(cell, { size: 11 });
      align(cell, 'left', false);
    });
    setMerged(
      this.sheet,
      titleRow,
      5,
      COLS,
      `Title : ${model.signer.title}`,
      (cell) => {
        styleFont(cell, { size: 11 });
        align(cell, 'left', false);
      },
    );

    const emailRow = this.nextRow(18);
    setMerged(this.sheet, emailRow, 1, 3, 'Email :', (cell) => {
      styleFont(cell, { size: 11 });
      align(cell, 'left', false);
    });
    setMerged(
      this.sheet,
      emailRow,
      5,
      COLS,
      `Email : ${model.signer.email}`,
      (cell) => {
        styleFont(cell, { size: 11, color: COLOR_LINK });
        align(cell, 'left', false);
      },
    );
  }

  async build(model: QuotationPreviewModel): Promise<ExcelJS.Workbook> {
    await this.addLogo();
    this.addTitle(model);
    this.addMeta(model);
    this.addProjectMeta(model);
    this.addLineItems(model);
    this.addTotals(model);
    this.addNotes(model);
    await this.addSignatures(model);
    return this.workbook;
  }
}

/**
 * Builds quotation Excel bytes that mirror QuotationPreview.
 */
export async function buildQuotationExcelBlob(
  quote: Quotation,
  currentUser?: PreviewUser,
): Promise<Blob | null> {
  try {
    const model = buildQuotationPreviewModel(quote, { currentUser });
    const builder = new PreviewExcelBuilder();
    const workbook = await builder.build(model);
    const buffer = await workbook.xlsx.writeBuffer();
    return new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
  } catch (error: unknown) {
    console.error('Error generating Excel quotation:', error);
    const message = error instanceof Error ? error.message : String(error);
    alert(`生成 Excel 报价单失败：${message}`);
    return null;
  }
}

/**
 * Generates and downloads a quotation Excel file matching preview.
 */
export async function downloadQuotationExcel(
  quote: Quotation,
  currentUser?: PreviewUser,
): Promise<boolean> {
  const blob = await buildQuotationExcelBlob(quote, currentUser);
  if (!blob) return false;

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = buildQuotationExportFileName(quote, 'xlsx');
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
  return true;
}
