import { extractErrorMessage } from '../../utils/api.js'

const EXISTING_APPROVAL_MESSAGE_RE =
  /ongoing recharge approval|already has an ongoing recharge approval|已存在进行中的充值审批单|已有进行中的充值审批单/i

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
