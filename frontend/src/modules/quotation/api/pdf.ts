import { getAccessToken, getApiBaseUrl, ApiError } from './client';

export async function renderHtmlToPdfBlob(html: string, fileName = 'quotation.pdf'): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(`${getApiBaseUrl()}/pdf/from-html`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ html, file_name: fileName }),
  });

  if (!response.ok) {
    let detail = `PDF generation failed (${response.status})`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status);
  }

  return response.blob();
}
