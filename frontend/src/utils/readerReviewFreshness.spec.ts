import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { chapterContentHash, readerReviewMatchesContent } from './readerReviewFreshness'

describe('reader simulation stays attached to its exact draft', () => {
  it('hashes unmodified UTF-8 prose using the backend contract', async () => {
    const text = '他没再叫她师姐。\r\n窗台上还留着那封信。'
    const hash = await chapterContentHash(text)
    expect(hash).toBe(createHash('sha256').update(text, 'utf8').digest('hex'))
    expect(hash).not.toBe(await chapterContentHash(text.replace('\r\n', '\n')))
  })

  it('hides a previous draft even when its reader liked the ending', async () => {
    const originalHash = await chapterContentHash('她把信收了起来。')
    const changedHash = await chapterContentHash('她把信烧了。')
    const report = { status: 'completed', source_sha256: originalHash, would_continue: true }
    expect(readerReviewMatchesContent(report, originalHash)).toBe(true)
    expect(readerReviewMatchesContent(report, changedHash)).toBe(false)
  })

  it('does not treat absent hashes, pending verification, or unavailable reviews as usable', async () => {
    const hash = await chapterContentHash('他终于回头。')
    expect(readerReviewMatchesContent({ status: 'completed' }, hash)).toBe(false)
    expect(readerReviewMatchesContent({ status: 'completed', source_sha256: hash }, null)).toBe(false)
    expect(readerReviewMatchesContent({ status: 'unavailable', source_sha256: hash }, hash)).toBe(false)
    expect(readerReviewMatchesContent({ status: 'partial', source_sha256: hash }, hash)).toBe(true)
  })
})
