/**
 * 清理章节版本正文：LLM 偶发把正文包成 JSON（{content: ...} 等）或带转义序列落库，
 * 展示前统一提取纯文本。此逻辑此前在 5 个组件里各复制一份（WritingDesk / WDWorkspace /
 * ChapterContent / VersionSelector / WDVersionDetailModal），现收敛到这里，存量逐步迁移。
 */
export const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: unknown): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          const nested = extractContent((value as Record<string, unknown>)[key])
          if (nested) return nested
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      content = extracted
    }
  } catch {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}
