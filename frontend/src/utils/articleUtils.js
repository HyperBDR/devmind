/**
 * Article utility functions
 */

/**
 * Map article status to StatusBadge status
 * @param {string} status - Article status
 * @returns {string} Mapped status for StatusBadge component
 */
export const mapArticleStatus = (status) => {
  const statusMap = {
    pending: 'pending',
    processing: 'processing',
    completed: 'completed',
    failed: 'failed'
  }
  return statusMap[status] || 'pending'
}

/**
 * Get format label for storage URL format
 * @param {string} format - Format key
 * @param {Function} t - i18n translation function
 * @returns {string} Translated format label
 */
export const getFormatLabel = (format, t) => {
  const formatLabels = {
    markdown_json: t('articles.formatMarkdownJson'),
    douyin_markdown: t('articles.formatDouyinMarkdown'),
    wechat_html: t('articles.formatWechatHtml'),
    wechat_markdown: t('articles.formatWechatMarkdown'),
    toutiao: t('articles.formatToutiao'),
    csdn: t('articles.formatCsdn')
  }
  return formatLabels[format] || format
}
