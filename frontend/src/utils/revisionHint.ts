/** 大纲滚动修订提示：后端存对象，前端只展示作者能读的句子。 */
export interface OutlineRevisionHint {
  source_chapter?: number
  severity?: string
  reason?: string
  suggestion?: string
  status?: string
  hint?: string
}

export type RevisionHintValue = string | OutlineRevisionHint | null | undefined

export function formatRevisionHint(hint: RevisionHintValue): string {
  if (hint == null || hint === '') return ''
  if (typeof hint === 'string') return hint.trim()
  const reason = typeof hint.reason === 'string' ? hint.reason.trim() : ''
  const suggestion = typeof hint.suggestion === 'string' ? hint.suggestion.trim() : ''
  if (reason && suggestion) return `${reason}。建议：${suggestion}`
  if (suggestion) return suggestion
  if (reason) return reason
  return typeof hint.hint === 'string' ? hint.hint.trim() : ''
}
