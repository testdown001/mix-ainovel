type OverviewDimension = 'pacing' | 'character' | 'worldbuilding' | 'tension'

export interface OverviewReviewAnalysis {
  overall_score: number
  dimensions: Record<string, number>
  reviewed_chapters: number
}

export interface OverviewReviewChapter {
  version_metadata?: Array<{ ai_review?: { scores?: Record<string, number> } }> | null
  recommended_version_index?: number | null
}

function score(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null
}

function average(values: Array<number | null>): number | null {
  const present = values.filter((value): value is number => value !== null)
  return present.length ? Math.round(present.reduce((sum, value) => sum + value, 0) / present.length) : null
}

export function getChapterReviewScore(chapter: OverviewReviewChapter): number | null {
  const scores = chapter.version_metadata?.[chapter.recommended_version_index ?? 0]?.ai_review?.scores
  if (!scores) return null
  return score(scores.overall) ?? score(scores.total) ?? average(Object.values(scores).map(score))
}

// Missing review data stays missing. Word counts and completion rates cannot assess story quality.
export function getOverviewReviewScores(
  analysis: OverviewReviewAnalysis | null | undefined,
  chapters: OverviewReviewChapter[] = [],
): Record<OverviewDimension, number | null> {
  if (analysis && analysis.reviewed_chapters > 0) {
    const dimensions = analysis.dimensions
    return {
      pacing: score(dimensions.pacing),
      character: score(dimensions.character_depth),
      worldbuilding: average([score(dimensions.consistency), score(dimensions.prose_quality)]),
      tension: average([score(dimensions.foreshadowing), score(dimensions.emotion_curve)]),
    }
  }
  const groups: Record<OverviewDimension, number[]> = { pacing: [], character: [], worldbuilding: [], tension: [] }
  const mapping: Record<string, OverviewDimension> = {
    pacing: 'pacing', rhythm: 'pacing', '节奏': 'pacing',
    character: 'character', characterization: 'character', character_depth: 'character', '人物': 'character',
    worldbuilding: 'worldbuilding', world: 'worldbuilding', immersion: 'worldbuilding',
    consistency: 'worldbuilding', prose_quality: 'worldbuilding', '世界观': 'worldbuilding',
    tension: 'tension', plot: 'tension', hook: 'tension',
    foreshadowing: 'tension', emotion_curve: 'tension', '张力': 'tension', '情节': 'tension',
  }
  for (const chapter of chapters) {
    const scores = chapter.version_metadata?.[chapter.recommended_version_index ?? 0]?.ai_review?.scores
    for (const [key, raw] of Object.entries(scores ?? {})) {
      const value = score(raw)
      const dimension = mapping[key.toLowerCase()]
      if (dimension && value !== null) groups[dimension].push(value)
    }
  }
  return {
    pacing: average(groups.pacing), character: average(groups.character),
    worldbuilding: average(groups.worldbuilding), tension: average(groups.tension),
  }
}

export function getOverviewReviewQuality(
  analysis: OverviewReviewAnalysis | null | undefined,
  chapters: OverviewReviewChapter[] = [],
): number | null {
  if (analysis && analysis.reviewed_chapters > 0 && score(analysis.overall_score) !== null) return analysis.overall_score
  const chapterAverage = average(chapters.map(getChapterReviewScore))
  return chapterAverage ?? average(Object.values(getOverviewReviewScores(analysis, chapters)))
}
