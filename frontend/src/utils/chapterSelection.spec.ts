import { describe, expect, it } from 'vitest'
import { chapterSelectionBaseline } from './chapterSelection'
import type { Chapter } from '@/api/novel'

const chapter = { revision_id: 12, content_hash: 'seen-hash',
  version_metadata: [{ version_id: 31 }, { version_id: 42 }] } as Chapter

describe('chapter selection uses the exact manuscript baseline and stable candidate identity', () => {
  it('captures stable ID rather than relying only on a mutable latest-batch index', () => {
    expect(chapterSelectionBaseline(chapter, 1)).toEqual({
      version_id: 42, expected_revision_id: 12, expected_content_hash: 'seen-hash',
    })
  })
  it('does not fabricate a baseline for stale or partially loaded chapters', () => {
    expect(() => chapterSelectionBaseline(undefined, 0)).toThrow('刷新')
    expect(() => chapterSelectionBaseline({ ...chapter, content_hash: null }, 0)).toThrow('刷新')
    expect(() => chapterSelectionBaseline(chapter, 9)).toThrow('刷新')
  })
})
