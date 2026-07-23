import { getAccessToken, getApiBaseUrl, ApiError } from './client';

async function pdfResponse(response: Response): Promise<Blob> {
  if (!response.ok) {
    let detail = `PDF generation failed (${response.status})`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // Keep the status-based fallback when the response is not JSON.
    }
    throw new ApiError(
      typeof detail === 'string' ? detail : JSON.stringify(detail),
      response.status,
    );
  }

  const blob = await response.blob();
  const signature = await blob.slice(0, 5).text();
  if (signature !== '%PDF-') {
    throw new ApiError('PDF generation returned an invalid file', 502);
  }
  return blob;
}

export async function renderExcelToPdfBlob(
  excelBlob: Blob,
  fileName = 'quotation.xlsx',
): Promise<Blob> {
  const token = getAccessToken();
  const form = new FormData();
  form.append('file', excelBlob, fileName);
  const response = await fetch(`${getApiBaseUrl()}/pdf/from-excel`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: form,
  });
  return pdfResponse(response);
}

export async function renderHtmlToPdfBlob(
  html: string,
  fileName = 'quotation.pdf',
): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(`${getApiBaseUrl()}/pdf/from-html`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ html, file_name: fileName }),
  });
  return pdfResponse(response);
}
