import { apiRequest } from './client'

export interface QuotationNote {
  id: string
  authorName: string
  authorEmail: string
  content: string
  createdAt: string
  updatedAt: string
  canEdit: boolean
}

interface ApiQuotationNote {
  id: string
  author_name: string
  author_email: string
  content: string
  created_at: string
  updated_at: string
  can_edit: boolean
}

function mapNote(note: ApiQuotationNote): QuotationNote {
  return {
    id: note.id,
    authorName: note.author_name,
    authorEmail: note.author_email,
    content: note.content,
    createdAt: note.created_at,
    updatedAt: note.updated_at,
    canEdit: note.can_edit
  }
}

export async function listQuotationNotes(
  quotationId: string
): Promise<QuotationNote[]> {
  const data = await apiRequest<{
    items: ApiQuotationNote[]
    total: number
  }>(`/quotations/${quotationId}/notes`)
  return data.items.map(mapNote)
}

export async function createQuotationNote(
  quotationId: string,
  content: string
): Promise<QuotationNote> {
  const note = await apiRequest<ApiQuotationNote>(
    `/quotations/${quotationId}/notes`,
    {
      method: 'POST',
      body: JSON.stringify({ content })
    }
  )
  return mapNote(note)
}

export async function updateQuotationNote(
  quotationId: string,
  noteId: string,
  content: string
): Promise<QuotationNote> {
  const note = await apiRequest<ApiQuotationNote>(
    `/quotations/${quotationId}/notes/${noteId}`,
    {
      method: 'PUT',
      body: JSON.stringify({ content })
    }
  )
  return mapNote(note)
}

export async function deleteQuotationNote(
  quotationId: string,
  noteId: string
): Promise<void> {
  await apiRequest<void>(`/quotations/${quotationId}/notes/${noteId}`, {
    method: 'DELETE'
  })
}
