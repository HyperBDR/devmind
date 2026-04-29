import { extractErrorMessage } from '../../utils/api.js'

const EXISTING_APPROVAL_MESSAGE_RE =
  /ongoing recharge approval|already has an ongoing recharge approval|已存在进行中的充值审批单|已有进行中的充值审批单/i

const MISSING_FIELDS_RE = /missing required fields?:\s*(.+)/i

export function getRechargeApprovalSubmitErrorContext(error) {
  const rawMessage = extractErrorMessage(error, '')
  const responseData = error?.response?.data
  const inner =
    responseData?.data && typeof responseData.data === 'object'
      ? responseData.data
      : responseData || {}

  return {
    message: rawMessage,
    existingApproval:
      typeof rawMessage === 'string' &&
      EXISTING_APPROVAL_MESSAGE_RE.test(rawMessage),
    instanceCode:
      inner.instance_code || inner.instanceCode || inner.instance || '',
    recordId: inner.record_id ?? inner.recordId ?? '',
    approvalCode: inner.approval_code || inner.approvalCode || ''
  }
}

export function getRechargeInfoSaveErrorContext(error) {
  const responseData = error?.response?.data

  // Primary: { recharge_info: ["missing required fields: ..."] }
  const fieldError = responseData?.recharge_info
  let inner = null
  if (fieldError !== undefined) {
    inner = Array.isArray(fieldError)
      ? fieldError
      : typeof fieldError === 'object' && fieldError !== null
        ? fieldError
        : [fieldError]
  } else {
    inner = Array.isArray(responseData) ? responseData : [responseData]
  }

  let missingFields = []

  for (const item of inner) {
    if (typeof item === 'string') {
      const match = item.match(MISSING_FIELDS_RE)
      if (match) {
        missingFields.push(...match[1].split(',').map((f) => f.trim()))
      }
    } else if (typeof item === 'object' && item !== null) {
      for (const values of Object.values(item)) {
        if (Array.isArray(values)) {
          for (const v of values) {
            const match = String(v).match(MISSING_FIELDS_RE)
            if (match) {
              missingFields.push(...match[1].split(',').map((f) => f.trim()))
            }
          }
        }
      }
    }
  }

  if (!missingFields.length) {
    const rawMessage = extractErrorMessage(error, '')
    const msgMatch = rawMessage.match(MISSING_FIELDS_RE)
    if (msgMatch) {
      missingFields = msgMatch[1].split(',').map((f) => f.trim())
    }
  }

  return {
    missingFields: missingFields.filter(Boolean)
  }
}
