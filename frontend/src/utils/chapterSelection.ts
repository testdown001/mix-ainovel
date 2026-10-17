import type { Chapter } from '@/api/novel'

/** Capture the baseline the author actually saw; never refresh it behind a selection. */
export function chapterSelectionBaseline(chapter: Chapter | undefined, versionIndex: number) {
  const versionId = chapter?.version_metadata?.[versionIndex]?.version_id
  if (!chapter || !Number.isInteger(versionId) || !versionId ||
      !Number.isInteger(chapter.revision_id) || typeof chapter.content_hash !== 'string') {
    throw new Error('章节版本信息不完整，请刷新章节后再选择正文')
  }
  return {
    version_id: versionId,
    expected_revision_id: chapter.revision_id as number,
    expected_content_hash: chapter.content_hash,
  }
}
