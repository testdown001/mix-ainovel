import { describe, expect, it } from 'vitest'
import { formatRevisionHint } from './revisionHint'

describe('formatRevisionHint', () => {
  it('reads reason + suggestion from the backend object', () => {
    expect(
      formatRevisionHint({
        source_chapter: 30,
        severity: 'medium',
        reason: '前文已揭开身份',
        suggestion: '改为余波与代价',
        status: 'pending',
      }),
    ).toBe('前文已揭开身份。建议：改为余波与代价')
  })

  it('does not stringify the whole object', () => {
    const text = formatRevisionHint({ reason: '瞳色冲突', suggestion: '' })
    expect(text).toBe('瞳色冲突')
    expect(text).not.toContain('[object Object]')
  })

  it('keeps a plain string', () => {
    expect(formatRevisionHint('下一章收束这条线')).toBe('下一章收束这条线')
  })
})
