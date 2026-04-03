// 门下省审核 API
import { requestJson } from './http'

export interface GatekeeperIssue {
  type: string
  severity: 'low' | 'medium' | 'high'
  description: string
  suggestion?: string
}

export interface GatekeeperReview {
  id: number
  project_id: string
  chapter_number: number
  approved: boolean
  overall_score: number
  scores: Record<string, number>
  issues: GatekeeperIssue[]
  review_comment?: string
  rewrite_required: boolean
  created_at: string
}

// 执行审核
export async function runGatekeeperReview(
  projectId: string,
  chapterNumber: number,
  chapterVersionId?: number
): Promise<{ review: GatekeeperReview }> {
  return requestJson(`/api/review/gatekeeper`, {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      chapter_number: chapterNumber,
      chapter_version_id: chapterVersionId,
    }),
  })
}

// 获取审核结果
export async function getGatekeeperReview(
  projectId: string,
  chapterNumber: number
): Promise<{ review: GatekeeperReview | null }> {
  return requestJson(`/api/review/gatekeeper/${projectId}/${chapterNumber}`)
}

export interface ProjectAnalysis {
  overall_score: number
  dimensions: Record<string, number>
  reviewed_chapters: number
}

export async function getProjectAnalysis(
  projectId: string
): Promise<{ analysis: ProjectAnalysis | null }> {
  return requestJson(`/api/review/analysis/${projectId}`)
}
