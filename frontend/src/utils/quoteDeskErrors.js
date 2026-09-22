const ENGLISH = 'en'

function isEnglish() {
  return String(localStorage.getItem('userLanguage') || '').toLowerCase().startsWith(ENGLISH)
}

function message(zh, en) {
  return isEnglish() ? en : zh
}

export function extractQuoteDeskErrorDetail(payload) {
  if (!payload || typeof payload !== 'object') return String(payload || '')

  const direct = payload.detail ?? payload.message
  if (direct) {
    return typeof direct === 'string' ? direct : JSON.stringify(direct)
  }

  return Object.entries(payload)
    .flatMap(([field, value]) => {
      const values = Array.isArray(value) ? value : [value]
      return values.map((item) => `${field}: ${String(item)}`)
    })
    .join(' ')
}

export function isQuoteDeskPath(path = '') {
  const value = String(path || '').toLowerCase()
  return value.includes('/v1/quotation') || value.includes('/v1/invoice')
}

export function quoteDeskErrorMessage(status, path = '', detail = '') {
  const url = String(path || '').toLowerCase()
  const text = String(detail || '').toLowerCase()

  if (
    (text.includes('quote_no') || text.includes('invoice_no')) &&
    (text.includes('already exists') || text.includes('unique'))
  ) {
    return message(
      '编号已存在，请更换一个唯一编号。',
      'This number is already in use. Please enter a unique number.',
    )
  }
  if (text.includes('quotation not found') || text.includes('invoice not found')) {
    return message(
      '找不到该内容，可能已被删除，或当前账号没有查看权限。',
      'This content could not be found. It may have been deleted, or you may not have permission to view it.',
    )
  }
  if (text.includes('document-imported quotations are read-only')) {
    return message(
      '该报价来自文件导入，当前为只读状态，不能直接修改。',
      'This quote was imported from a file and is read-only.',
    )
  }
  if (text.includes('document-imported quotations cannot be copied')) {
    return message(
      '导入报价不能直接复制，请新建报价单。',
      'Imported quotes cannot be copied. Please create a new quote instead.',
    )
  }
  if (text.includes('file required')) {
    return message('请选择要上传的文件。', 'Select a file to upload.')
  }
  if (text.includes('folder not found')) {
    return message(
      '找不到该目录，请刷新后重新选择。',
      'This folder could not be found. Refresh and select another folder.',
    )
  }
  if (text.includes('user not found')) {
    return message(
      '该用户不存在或已被停用。',
      'This user does not exist or has been deactivated.',
    )
  }
  if (text === 'forbidden' || text.includes('permission required')) {
    return message(
      '当前账号没有执行此操作的权限，请联系管理员申请权限。',
      'You don’t have permission to perform this action. Please contact your administrator to request access.',
    )
  }
  if (text.includes('only the author can change this note')) {
    return message(
      '只有便笺作者可以修改或删除此便笺。',
      'Only the note author can edit or delete this note.',
    )
  }
  if (text.includes('document is archived') || text.includes('attachment is archived')) {
    return message(
      '该文件已归档，当前不能执行此操作。',
      'This file has been archived and cannot be used for this action.',
    )
  }
  if (text.includes('folder picker is disabled')) {
    return message(
      '飞书目录选择功能当前未启用，请联系管理员。',
      'Feishu folder selection is currently unavailable. Please contact your administrator.',
    )
  }
  if (text.includes('no authorized feishu folders')) {
    return message(
      '当前账号没有可访问的飞书目录，请联系管理员授权。',
      'You don’t have access to any Feishu folders. Please contact your administrator.',
    )
  }
  if (text.includes('archive folder sync already running')) {
    return message(
      '飞书目录同步正在进行，请稍后再试。',
      'A Feishu folder sync is already in progress. Please try again later.',
    )
  }
  if (text.includes('export job not found')) {
    return message(
      '导出任务已失效，请重新发起导出。',
      'This export job is no longer available. Please start a new export.',
    )
  }
  if (text.includes('rendered assets are unavailable')) {
    return message(
      '生成的文件暂不可用，请稍后重试。',
      'The generated file is not currently available. Please try again later.',
    )
  }
  if (text.includes('invalid pagination')) {
    return message(
      '分页参数无效，请刷新页面后重试。',
      'The pagination parameters are invalid. Refresh the page and try again.',
    )
  }
  if (text.includes('invalid lifecycle') || text.includes('invalid doc_type')) {
    return message(
      '文件状态或类型无效，请刷新页面后重试。',
      'The file status or type is invalid. Refresh the page and try again.',
    )
  }

  if (status === 401) {
    return message('登录已过期，请重新登录。', 'Your session has expired. Please sign in again.')
  }
  if (status === 403) {
    if (url.includes('/invoice/')) {
      return message(
        '当前账号没有发票查看权限，请联系管理员申请票据平台访问权限。',
        'You don’t have permission to view invoices. Please contact your Quote Desk admin to request Invoice workspace access.',
      )
    }
    if (url.includes('upload') || text.includes('upload access')) {
      return message(
        '当前账号没有向该目录上传文件的权限，请联系管理员授权。',
        'You don’t have permission to upload files to this folder. Please contact your administrator to request upload access.',
      )
    }
    if (url.includes('permission') || url.includes('membership')) {
      return message(
        '只有 Quote Desk 管理员可以管理权限，请联系管理员处理。',
        'Only Quote Desk admins can manage permissions.',
      )
    }
    return message(
      '当前账号没有访问该 Quote Desk 内容的权限，请联系管理员申请访问权限。',
      'You don’t have permission to access this Quote Desk content. Please contact your administrator to request access.',
    )
  }
  if (status === 404) {
    return message(
      '找不到该内容，可能已被删除，或当前账号没有查看权限。',
      'This content could not be found. It may have been deleted, or you may not have permission to view it.',
    )
  }
  if (status === 409) {
    return message(
      '当前操作与已有任务冲突，请稍后重试。',
      'This action conflicts with another operation. Please try again later.',
    )
  }
  if (status === 422) {
    return message(
      '文件处理失败，请检查文件内容后重试。',
      'We couldn’t process this file. Check its contents and try again.',
    )
  }
  if (status >= 500) {
    return message(
      '服务暂时不可用，请稍后重试；如果问题持续，请联系管理员。',
      'The service is temporarily unavailable. Please try again later. If the problem persists, contact your administrator.',
    )
  }
  return ''
}
