import type { Quotation } from '../types';
import { buildQuotationExportBaseName, buildQuotationExportFileName } from './quotationFileName';
import { buildQuotationPreviewModel } from './quotationPreviewModel';
import type { PreviewLineItem, PreviewUser } from './quotationPreviewModel';

const oneProLogoUrl = new URL('../assets/onepro-logo.png', import.meta.url).href;

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function money(value: number): string {
  if (!value) return '';
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
}

function percent(value: number): string {
  return value ? `${value}%` : '0%';
}

function toAbsoluteAssetUrl(url: string): string {
  if (/^https?:\/\//.test(url) || url.startsWith('data:')) {
    return url;
  }
  if (typeof window === 'undefined') {
    return url;
  }
  try {
    return new URL(url, window.location.origin).href;
  } catch {
    return url;
  }
}

async function toEmbeddedAssetUrl(url: string): Promise<string> {
  const absolute = toAbsoluteAssetUrl(url);
  if (absolute.startsWith('data:')) return absolute;
  if (typeof window === 'undefined' || typeof fetch === 'undefined') return absolute;

  try {
    const response = await fetch(absolute);
    if (!response.ok) return absolute;
    const blob = await response.blob();
    return await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || absolute));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return absolute;
  }
}

function cell(content: string, colSpan = 1, className = ''): string {
  return `<td colspan="${colSpan}" class="cell ${className}">${content}</td>`;
}

function noBorder(content: string, colSpan = 1, className = ''): string {
  return `<td colspan="${colSpan}" class="no-border ${className}">${content}</td>`;
}

function boxCell(content: string, colSpan = 1, className = ''): string {
  const display = content || '&nbsp;';
  return `<td colspan="${colSpan}" class="box-cell ${className}">${display}</td>`;
}

function metaLabel(content: string): string {
  return noBorder(content, 1, 'meta-label');
}

function metaValue(content: string): string {
  return noBorder(escapeHtml(content), 1, 'meta-value mono');
}

function lineCell(content: string, className = ''): string {
  return `<td class="cell ${className}">${content || '&nbsp;'}</td>`;
}

function renderLineRows(rows: PreviewLineItem[]): string {
  return rows.map(item => {
    const hasContent = Boolean(item.name || item.description);
    const description = item.description || item.name || '';
    return `
    <tr class="line-item">
      ${lineCell(hasContent ? String(item.lineNo) : '', 'center mono')}
      ${lineCell(escapeHtml(description), 'desc')}
      ${lineCell(hasContent ? String(item.qty) : '', 'center mono')}
      ${lineCell(hasContent ? money(item.listPrice) : '', 'right mono')}
      ${lineCell(hasContent ? percent(item.discountPercent) : '', 'center mono')}
      ${lineCell(hasContent ? money(item.netUnitPrice) : '', 'right mono')}
      ${lineCell(hasContent ? money(item.extendedPrice) : '', 'right mono')}
    </tr>
  `;
  }).join('');
}

export function buildPrintableQuotationHtml(
  quote: Quotation,
  currentUser?: PreviewUser,
  options?: { logoUrl?: string; autoPrint?: boolean },
): string {
  const model = buildQuotationPreviewModel(quote, { currentUser });
  const logoUrl = options?.logoUrl || toAbsoluteAssetUrl(oneProLogoUrl);
  const documentTitle = buildQuotationExportBaseName(quote);
  const autoPrintScript = options?.autoPrint
    ? `
  <script>
    window.addEventListener('load', function () {
      window.setTimeout(function () { window.print(); }, 200);
    });
  </script>`
    : '';

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(documentTitle)}</title>
  <style>
    @page { size: A4; margin: 12mm; }
    * { box-sizing: border-box; }
    html, body {
      width: 210mm;
      min-height: 297mm;
    }
    body {
      position: relative;
      margin: 0;
      padding: 28px;
      color: #0f172a;
      background: #ffffff;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 11px;
      line-height: 1.35;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    tr { break-inside: avoid; page-break-inside: avoid; }
    col.col-1 { width: 13%; }
    col.col-2 { width: 26%; }
    col.col-3 { width: 8%; }
    col.col-4 { width: 12%; }
    col.col-5 { width: 11%; }
    col.col-6 { width: 16%; }
    col.col-7 { width: 14%; }
    td { vertical-align: middle; }
    .cell { border: 1px solid #cbd5e1; padding: 4px 6px; }
    .no-border { border: 0; padding: 4px 6px; }
    .box-cell { border: 1px solid #0f172a; padding: 4px 6px; min-height: 32px; }
    tr.line-item td { height: 32px; min-height: 32px; }
    .box-header { background: #e2e8f0; font-weight: 700; text-align: center; }
    .meta-label { text-align: right; font-weight: 700; white-space: nowrap; padding-right: 4px; }
    .meta-value { border-bottom: 1px solid #0f172a; text-align: right; padding-bottom: 2px; }
    .section-header .cell { background: #e2e8f0; font-weight: 700; font-size: 13px; }
    .soft-header .cell { background: #f8fafc; font-weight: 700; text-align: center; }
    .notes { white-space: pre-line; line-height: 1.45; font-size: 9px; background: #f8fafc; color: #334155; }
    .center { text-align: center; }
    .right { text-align: right; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .title-spacer { height: 112px; }
    .spacer-row td { border: 0; height: 16px; padding: 0; }
    .logo { position: absolute; left: 28px; top: 28px; width: 166px; height: auto; }
    .company-title { text-align: center; font-size: 18px; font-weight: 700; }
    .doc-title { text-align: center; font-size: 22px; font-weight: 700; text-decoration: underline; }
    .signature-area { position: relative; min-height: 40px; padding-bottom: 2px; }
    .signature-line-bar { border-bottom: 1px solid #0f172a; height: 0; }
    .signature-image { position: absolute; left: 0; bottom: 4px; max-height: 32px; max-width: 100%; object-fit: contain; object-position: left bottom; }
    .email-link { color: #2563eb; text-decoration: none; }
  </style>
</head>
<body>
  <img class="logo" src="${escapeHtml(logoUrl)}" alt="OnePro" />
  <table>
    <colgroup>
      <col class="col-1" />
      <col class="col-2" />
      <col class="col-3" />
      <col class="col-4" />
      <col class="col-5" />
      <col class="col-6" />
      <col class="col-7" />
    </colgroup>
    <tbody>
      <tr class="title-spacer"><td colspan="7" class="no-border"></td></tr>
      <tr><td colspan="7" class="no-border company-title">${escapeHtml(model.issuerCompanyName)}</td></tr>
      <tr><td colspan="7" class="no-border doc-title">Quotation</td></tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr>
        ${noBorder('', 5)}
        ${metaLabel('Date:')}
        ${metaValue(model.quoteDate)}
      </tr>
      <tr>
        ${boxCell('Ship to', 2, 'box-header')}
        ${noBorder('', 3)}
        ${metaLabel('Quote No.:')}
        ${metaValue(model.quoteNo)}
      </tr>
      <tr>
        ${boxCell(`<strong>Company :</strong> ${escapeHtml(model.customerCompany || '')}`, 2)}
        ${noBorder('', 3)}
        ${metaLabel('Quote Valid Till:')}
        ${metaValue(model.validTill)}
      </tr>
      <tr>
        ${boxCell(`<strong>Name :</strong> ${escapeHtml(model.contactPerson || '')}`, 2)}
        ${noBorder('', 5)}
      </tr>
      <tr>
        ${boxCell(`<strong>Email :</strong> ${escapeHtml(model.email || '')}`, 2)}
        ${noBorder('', 5)}
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr>
        ${boxCell('Bill to:', 2, 'box-header')}
        ${noBorder('', 5)}
      </tr>
      <tr>
        ${boxCell(`<strong>Company :</strong> ${escapeHtml(model.billingCompany || '')}`, 2)}
        ${noBorder('', 5)}
      </tr>
      <tr>
        ${boxCell(`<strong>Name :</strong> ${escapeHtml(model.billingContact || '')}`, 2)}
        ${noBorder('', 5)}
      </tr>
      <tr>
        ${boxCell(`<strong>Email :</strong> ${escapeHtml(model.billingEmail || '')}`, 2)}
        ${noBorder('', 5)}
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr class="section-header">
        ${cell('Contact Person')}
        ${cell('Email')}
        ${cell('Project', 3)}
        ${cell('Payment Terms')}
        ${cell('Currency')}
      </tr>
      <tr>
        ${cell(escapeHtml(model.signer.name))}
        ${cell(escapeHtml(model.signer.email))}
        ${cell(escapeHtml(model.projectName || '-'), 3)}
        ${cell(escapeHtml(model.paymentTerms || '-'))}
        ${cell(escapeHtml(model.currency), 1, 'mono')}
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr class="section-header">
        ${cell('Software', 7)}
      </tr>
      <tr class="soft-header">
        ${cell('Item')}
        ${cell('Description')}
        ${cell('Qty')}
        ${cell('List Price')}
        ${cell('Discount (%)')}
        ${cell('Discounted Price')}
        ${cell('Extended Price')}
      </tr>
      ${renderLineRows(model.softwareRows)}
      <tr>
        ${noBorder('', 5)}
        ${cell('Software subscription subtotal:', 1, 'right')}
        ${cell(`<strong>${money(model.softwareSubtotal)}</strong>`, 1, 'right mono')}
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr class="section-header">
        ${cell('Others', 7)}
      </tr>
      <tr class="soft-header">
        ${cell('Item')}
        ${cell('Description')}
        ${cell('Qty')}
        ${cell('List Price')}
        ${cell('Discount (%)')}
        ${cell('Discounted Price')}
        ${cell('Extended Price')}
      </tr>
      ${renderLineRows(model.othersRows)}
      <tr>
        ${noBorder('', 5)}
        ${cell('Others Subtotal:', 1, 'right')}
        ${cell(`<strong>${money(model.othersSubtotal)}</strong>`, 1, 'right mono')}
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr>
        ${noBorder('', 5)}
        ${cell(`Subtotal before ${escapeHtml(model.taxLabel)}:`, 1, 'right')}
        ${cell(`<strong>${money(model.subtotalBeforeVat)}</strong>`, 1, 'right mono')}
      </tr>
      <tr>
        ${noBorder('', 5)}
        ${cell(`${escapeHtml(model.taxLabel)} Amount (${model.vatRate}%):`, 1, 'right')}
        ${cell(`<strong>${money(model.vatAmount)}</strong>`, 1, 'right mono')}
      </tr>
      <tr>
        ${noBorder('', 5)}
        ${cell('Grand Total:', 1, 'right')}
        ${cell(`<strong>${money(model.grandTotal)}</strong>`, 1, 'right mono grand-total')}
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border"></td></tr>
      <tr><td colspan="7" class="no-border"><strong>Additional Notes &amp; Disclaimers:</strong></td></tr>
      <tr><td colspan="7" class="cell notes">${escapeHtml(model.remarksDisclaimer)}</td></tr>
      <tr>
        <td colspan="7" class="no-border" style="padding-top:12px;">
          To indicate Customer acceptance of this quotation, please sign below and return one copy of this quotation to OnePro Cloud.
        </td>
      </tr>
      <tr class="spacer-row"><td colspan="7" class="no-border" style="height:32px;"></td></tr>
      <tr>
        ${noBorder('', 3)}
        ${noBorder('', 1)}
        ${noBorder(`<strong>${escapeHtml(model.issuerCompanyName)}</strong>`, 3)}
      </tr>
      <tr>
        ${noBorder('<div class="signature-area"><div class="signature-line-bar"></div></div>', 3, 'signature-area')}
        ${noBorder('', 1)}
        ${model.issuerSignature
          ? noBorder(`<div class="signature-area"><img class="signature-image" src="${model.issuerSignature}" alt="Issuer signature" /><div class="signature-line-bar"></div></div>`, 3, 'signature-area')
          : noBorder('<div class="signature-area"><div class="signature-line-bar"></div></div>', 3, 'signature-area')}
      </tr>
      <tr>
        ${noBorder('Name :', 3)}
        ${noBorder('', 1)}
        ${noBorder(`Name : ${escapeHtml(model.signer.name)}`, 3)}
      </tr>
      <tr>
        ${noBorder('Title :', 3)}
        ${noBorder('', 1)}
        ${noBorder(`Title : ${escapeHtml(model.signer.title)}`, 3)}
      </tr>
      <tr>
        ${noBorder('Email :', 3)}
        ${noBorder('', 1)}
        ${noBorder(`Email : <a class="email-link" href="mailto:${escapeHtml(model.signer.email)}">${escapeHtml(model.signer.email)}</a>`, 3)}
      </tr>
    </tbody>
  </table>
  ${autoPrintScript}
</body>
</html>`;
}

function waitForDocumentAssets(doc: Document): Promise<void> {
  const images = Array.from(doc.images || []);
  if (images.length === 0) {
    return Promise.resolve();
  }
  return Promise.all(
    images.map(
      (img) =>
        new Promise<void>((resolve) => {
          if (img.complete) {
            resolve();
            return;
          }
          img.addEventListener('load', () => resolve(), { once: true });
          img.addEventListener('error', () => resolve(), { once: true });
        }),
    ),
  ).then(() => undefined);
}

/**
 * Show the native browser print dialog (Save as PDF) with a working preview.
 * Keep a real A4-sized frame off-screen; opacity:0 / 0x0 frames print blank.
 *
 * Chrome names "Save as PDF" from the top-level document.title when printing
 * an iframe, so temporarily swap the parent title to the export file name.
 */
function printHtmlViaOffscreenFrame(
  html: string,
  downloadBaseName: string,
): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof document === 'undefined') {
      resolve(false);
      return;
    }

    const iframe = document.createElement('iframe');
    iframe.setAttribute('title', downloadBaseName);
    iframe.setAttribute('aria-hidden', 'true');
    iframe.style.cssText = [
      'position:fixed',
      'left:-10000px',
      'top:0',
      'width:794px',
      'height:1123px',
      'border:0',
      'margin:0',
      'padding:0',
      'background:#fff',
    ].join(';');

    let cleanedUp = false;
    let printStarted = false;
    let settled = false;
    const previousTitle = document.title;

    const restoreTitle = () => {
      document.title = previousTitle;
    };

    const cleanup = () => {
      if (cleanedUp) return;
      cleanedUp = true;
      iframe.onload = null;
      restoreTitle();
      iframe.remove();
    };

    const finish = (ok: boolean) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };

    iframe.onload = () => {
      // srcdoc can fire load more than once; only print a single time.
      if (printStarted) return;

      const win = iframe.contentWindow;
      const doc = iframe.contentDocument;
      if (!win || !doc?.body) {
        cleanup();
        finish(false);
        return;
      }

      printStarted = true;
      void waitForDocumentAssets(doc).then(() => {
        window.setTimeout(() => {
          try {
            document.title = downloadBaseName;
            if (doc.title !== downloadBaseName) {
              doc.title = downloadBaseName;
            }
            win.focus();
            win.print();
            win.addEventListener('afterprint', cleanup, { once: true });
            window.setTimeout(cleanup, 120_000);
            finish(true);
          } catch {
            cleanup();
            finish(false);
          }
        }, 100);
      });
    };

    document.body.appendChild(iframe);
    iframe.srcdoc = html;
  });
}

/**
 * Open the browser print dialog so users can preview and Save as PDF.
 * Does not open a separate browser tab/window.
 */
export async function downloadQuotationPdf(
  quote: Quotation,
  currentUser?: PreviewUser,
): Promise<boolean> {
  if (quote.status === 'Cancelled') {
    alert('提示：该报价单目前处于「已作废」状态，无法导出 PDF。');
    return false;
  }

  if (typeof document === 'undefined') {
    return false;
  }

  try {
    const logoUrl = await toEmbeddedAssetUrl(oneProLogoUrl);
    const downloadBaseName = buildQuotationExportBaseName(quote);
    const html = buildPrintableQuotationHtml(quote, currentUser, {
      logoUrl,
    });
    const printed = await printHtmlViaOffscreenFrame(html, downloadBaseName);
    if (printed) return true;
    alert('无法打开打印预览，请允许弹窗后重试，或稍后再试。');
    return false;
  } catch {
    alert('导出 PDF 失败，请稍后重试。');
    return false;
  }
}

/** HTML print draft for Feishu upload (browser "Save as PDF" equivalent content). */
export function buildQuotationPrintHtmlBlob(quote: Quotation, currentUser?: PreviewUser): Blob {
  const html = buildPrintableQuotationHtml(quote, currentUser);
  return new Blob([html], { type: 'text/html;charset=utf-8' });
}

/** Build printable HTML with embedded assets, then render a real PDF via backend Playwright. */
export async function buildQuotationPdfBlob(
  quote: Quotation,
  currentUser?: PreviewUser,
): Promise<Blob> {
  const { renderHtmlToPdfBlob } = await import('../api/pdf');
  const logoUrl = await toEmbeddedAssetUrl(oneProLogoUrl);
  const html = buildPrintableQuotationHtml(quote, currentUser, { logoUrl });
  const fileName = buildQuotationExportFileName(quote, 'pdf');
  return renderHtmlToPdfBlob(html, fileName);
}
