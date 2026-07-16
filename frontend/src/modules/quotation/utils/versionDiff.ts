import type { Quotation, QuotationLineItem, QuoteVersion } from '../types'

export type VersionDiffFieldKey =
  | 'projectName'
  | 'clientCompany'
  | 'contactPerson'
  | 'email'
  | 'billingCompany'
  | 'billingContact'
  | 'billingEmail'
  | 'currency'
  | 'paymentTerms'
  | 'status'
  | 'grandTotal'
  | 'taxLabel'
  | 'vatRate'
  | 'salesperson'
  | 'quoteDate'
  | 'expireDate'
  | 'remarksDisclaimer'

export interface VersionDiffResult {
  changedFields: Set<VersionDiffFieldKey>
  changedLineIds: Set<string>
  removedLineCount: number
  addedLineCount: number
  hasChanges: boolean
}

type SnapshotLike = Pick<
  QuoteVersion,
  | 'projectName'
  | 'clientCompany'
  | 'contactPerson'
  | 'email'
  | 'billingCompany'
  | 'billingContact'
  | 'billingEmail'
  | 'currency'
  | 'paymentTerms'
  | 'status'
  | 'grandTotal'
  | 'taxLabel'
  | 'vatRate'
  | 'salesperson'
  | 'quoteDate'
  | 'expireDate'
  | 'remarksDisclaimer'
  | 'items'
>

function normalizeText(value?: string | null): string {
  return (value || '').trim()
}

function normalizeNumber(value?: number | null): number {
  return Number(value) || 0
}

function lineFingerprint(item: QuotationLineItem): string {
  return [
    item.type,
    normalizeText(item.description || item.name),
    normalizeNumber(item.listPrice),
    normalizeNumber(item.discountPercent),
    normalizeNumber(item.qty),
    normalizeNumber(item.netUnitPrice),
    normalizeNumber(item.extendedPrice),
  ].join('|')
}

function lineMatchKey(item: QuotationLineItem): string {
  if (item.id) return `id:${item.id}`
  return `fp:${lineFingerprint(item)}`
}

/**
 * Diff a historical version against the current quote (latest).
 * Fields/lines present in the version but different from current
 * are marked as changed.
 */
export function diffVersionAgainstCurrent(
  version: SnapshotLike,
  current: Quotation,
): VersionDiffResult {
  const changedFields = new Set<VersionDiffFieldKey>()
  const fieldChecks: Array<[VersionDiffFieldKey, string | number]> = [
    ['projectName', normalizeText(version.projectName)],
    ['clientCompany', normalizeText(version.clientCompany)],
    ['contactPerson', normalizeText(version.contactPerson)],
    ['email', normalizeText(version.email)],
    ['billingCompany', normalizeText(version.billingCompany)],
    ['billingContact', normalizeText(version.billingContact)],
    ['billingEmail', normalizeText(version.billingEmail)],
    ['currency', normalizeText(version.currency)],
    ['paymentTerms', normalizeText(version.paymentTerms)],
    ['status', normalizeText(version.status)],
    ['grandTotal', normalizeNumber(version.grandTotal)],
    ['taxLabel', normalizeText(version.taxLabel)],
    ['vatRate', normalizeNumber(version.vatRate)],
    ['salesperson', normalizeText(version.salesperson)],
    ['quoteDate', normalizeText(version.quoteDate)],
    ['expireDate', normalizeText(version.expireDate)],
    ['remarksDisclaimer', normalizeText(version.remarksDisclaimer)],
  ]

  const currentValues: Record<VersionDiffFieldKey, string | number> = {
    projectName: normalizeText(current.projectName),
    clientCompany: normalizeText(current.clientCompany),
    contactPerson: normalizeText(current.contactPerson),
    email: normalizeText(current.email),
    billingCompany: normalizeText(current.billingCompany),
    billingContact: normalizeText(current.billingContact),
    billingEmail: normalizeText(current.billingEmail),
    currency: normalizeText(current.currency),
    paymentTerms: normalizeText(current.paymentTerms),
    status: normalizeText(current.status),
    grandTotal: normalizeNumber(current.grandTotal),
    taxLabel: normalizeText(current.taxLabel),
    vatRate: normalizeNumber(current.vatRate),
    salesperson: normalizeText(current.salesperson),
    quoteDate: normalizeText(current.quoteDate),
    expireDate: normalizeText(current.expireDate),
    remarksDisclaimer: normalizeText(current.remarksDisclaimer),
  }

  fieldChecks.forEach(([key, value]) => {
    if (value !== currentValues[key]) {
      changedFields.add(key)
    }
  })

  const currentByKey = new Map(
    (current.items || []).map((item) => [lineMatchKey(item), item]),
  )
  const versionKeys = new Set<string>()
  const changedLineIds = new Set<string>()
  let removedLineCount = 0

  ;(version.items || []).forEach((item) => {
    const key = lineMatchKey(item)
    versionKeys.add(key)
    const currentItem = currentByKey.get(key)
    if (!currentItem) {
      changedLineIds.add(item.id)
      removedLineCount += 1
      return
    }
    if (lineFingerprint(item) !== lineFingerprint(currentItem)) {
      changedLineIds.add(item.id)
    }
  })

  let addedLineCount = 0
  ;(current.items || []).forEach((item) => {
    if (!versionKeys.has(lineMatchKey(item))) {
      addedLineCount += 1
    }
  })

  const hasChanges =
    changedFields.size > 0 ||
    changedLineIds.size > 0 ||
    addedLineCount > 0

  return {
    changedFields,
    changedLineIds,
    removedLineCount,
    addedLineCount,
    hasChanges,
  }
}

export function isFieldChanged(
  diff: VersionDiffResult | null | undefined,
  field: VersionDiffFieldKey,
): boolean {
  return Boolean(diff?.changedFields.has(field))
}
