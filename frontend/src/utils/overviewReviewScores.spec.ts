import { describe, expect, it } from 'vitest'
import { getOverviewReviewQuality, getOverviewReviewScores } from './overviewReviewScores'
import type { OverviewReviewChapter } from './overviewReviewScores'

describe('overview quality uses review evidence', () => {
  it('does not turn more chapters or uniform word counts into quality scores', () => {
    const completed = Array.from({ length: 12 }, (_, index) => ({
      chapter_number: index + 1, generation_status: 'successful', word_count: 4000,
      version_metadata: null,
    }))
    expect(getOverviewReviewQuality(null, completed)).toBeNull()
    expect(getOverviewReviewScores(null, completed)).toEqual({
      pacing: null, character: null, worldbuilding: null, tension: null,
    })
    expect(getOverviewReviewQuality({ overall_score: 0, dimensions: { pacing: 0 }, reviewed_chapters: 0 }, completed)).toBeNull()
  })

  it('preserves a real zero score and distinguishes unassessed dimensions', () => {
    const reviewed = { overall_score: 0, dimensions: { pacing: 0, character_depth: 75 }, reviewed_chapters: 1 }
    expect(getOverviewReviewQuality(reviewed)).toBe(0)
    expect(getOverviewReviewScores(reviewed)).toEqual({
      pacing: 0, character: 75, worldbuilding: null, tension: null,
    })
  })

  it('retains version reviews when no aggregate review has run', () => {
    const chapters: OverviewReviewChapter[] = [{ recommended_version_index: 1, version_metadata: [
      { ai_review: { scores: { overall: 90, pacing: 95 } } },
      { ai_review: { scores: { overall: 62, pacing: 50, character: 74 } } },
    ] }]
    expect(getOverviewReviewQuality(null, chapters)).toBe(62)
    expect(getOverviewReviewScores(null, chapters)).toEqual({
      pacing: 50, character: 74, worldbuilding: null, tension: null,
    })
  })
})
