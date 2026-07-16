import ExcelJS from 'exceljs';
import type { DiscountOption, Product, Service } from '../types';

export interface TemplateCatalogs {
  products: Product[];
  services: Service[];
  discounts: DiscountOption[];
}

function cellText(value: ExcelJS.CellValue): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    if ('text' in value) return String(value.text ?? '').trim();
    if ('richText' in value) return value.richText.map(part => part.text).join('').trim();
    if ('result' in value) return String(value.result ?? '').trim();
    if ('formula' in value) return String(value.result ?? '').trim();
  }
  return String(value).trim();
}

function cellNumber(value: ExcelJS.CellValue): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const parsed = Number(cellText(value).replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : null;
}

function slug(value: string, fallback: string): string {
  const cleaned = value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 36);
  return cleaned || fallback;
}

function templateCode(prefix: string, value: string, index: number): string {
  return `${prefix}-${String(index).padStart(3, '0')}-${slug(value, 'ITEM')}`;
}

function parseThreshold(value: string): number | undefined {
  const match = value.match(/\d+/);
  return match ? Number(match[0]) : undefined;
}

function priceLabel(rawValue: ExcelJS.CellValue): { listPrice: number; pricingNote?: string } {
  const numeric = cellNumber(rawValue);
  if (numeric !== null) return { listPrice: numeric };
  const note = cellText(rawValue);
  return {
    listPrice: 0,
    pricingNote: note || 'Contact Sales',
  };
}

function scanRowCount(worksheet: ExcelJS.Worksheet): number {
  return Math.max(worksheet.rowCount, worksheet.actualRowCount);
}

export function extractTemplateCatalogs(workbook: ExcelJS.Workbook): TemplateCatalogs {
  const products: Product[] = [];
  const services: Service[] = [];
  const discounts: DiscountOption[] = [
    {
      id: 'disc-none',
      name: 'No Discount',
      percent: 0,
    },
  ];

  const softwareSheet = workbook.getWorksheet('SoftwareList');
  if (softwareSheet) {
    for (let rowNumber = 2; rowNumber <= scanRowCount(softwareSheet); rowNumber++) {
      const row = softwareSheet.getRow(rowNumber);
      const name = cellText(row.getCell(1).value);
      const vmQuantity = cellText(row.getCell(2).value);
      const { listPrice, pricingNote } = priceLabel(row.getCell(3).value);

      if (!name || name.toLowerCase() === 'others') continue;

      const code = templateCode('SW', name, rowNumber - 1);
      products.push({
        id: `tpl-product-${rowNumber}-${slug(name, 'software').toLowerCase()}`,
        name,
        code,
        listPrice,
        category: 'Software License',
        description: `License Type: ${name}. VM Quantity: ${vmQuantity || 'N/A'}. Cost: ${pricingNote || listPrice}.`,
        pricingNote,
        sourceSheet: 'SoftwareList',
        sourceRow: rowNumber,
      });
    }
  }

  const othersSheet = workbook.getWorksheet('OthersList');
  if (othersSheet) {
    for (let rowNumber = 2; rowNumber <= scanRowCount(othersSheet); rowNumber++) {
      const row = othersSheet.getRow(rowNumber);
      const description = cellText(row.getCell(1).value);
      const vmQuantity = cellText(row.getCell(2).value);
      const { listPrice, pricingNote } = priceLabel(row.getCell(3).value);
      const quantityMin = cellNumber(row.getCell(4).value) ?? undefined;
      const quantityMax = cellNumber(row.getCell(5).value) ?? undefined;

      if (!description || description.toLowerCase() === 'others') continue;

      const name = vmQuantity ? `${description} (${vmQuantity} VMs)` : description;
      const code = templateCode('OT', `${description}-${vmQuantity}`, rowNumber - 1);
      services.push({
        id: `tpl-service-${rowNumber}-${slug(`${description}-${vmQuantity}`, 'service').toLowerCase()}`,
        name,
        code,
        listPrice,
        unit: 'range',
        description: `Description: ${description}. VM Quantity: ${vmQuantity || 'N/A'}. Cost: ${pricingNote || listPrice}.`,
        quantityRange: vmQuantity,
        quantityMin,
        quantityMax,
        pricingNote,
        sourceSheet: 'OthersList',
        sourceRow: rowNumber,
      });
    }
  }

  const discountSheet = workbook.getWorksheet('Discount');
  if (discountSheet) {
    for (let rowNumber = 2; rowNumber <= scanRowCount(discountSheet); rowNumber++) {
      const row = discountSheet.getRow(rowNumber);
      const condition = cellText(row.getCell(2).value) || cellText(row.getCell(1).value);
      const rawRatio = cellNumber(row.getCell(3).value) ?? cellNumber(row.getCell(2).value);

      if (!condition || rawRatio === null) continue;

      const percent = rawRatio <= 1 ? Math.round(rawRatio * 100) : Math.round(rawRatio);
      discounts.push({
        id: `disc-threshold-${rowNumber}-${percent}`,
        name: `${condition} VM (${percent}% OFF)`,
        percent,
        condition,
        threshold: parseThreshold(condition),
        sourceSheet: 'Discount',
        sourceRow: rowNumber,
      });
    }
  }

  return { products, services, discounts };
}

export function formatCatalogPrice(value: number, pricingNote?: string): string {
  if (value > 0) return `USD ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return pricingNote || 'Contact Sales';
}
