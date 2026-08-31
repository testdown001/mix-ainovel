import { http } from '@/api/http'

export interface SkillInfo {
  id: string
  skill_id?: number
  name: string
  description: string
  version: string
  author: string
  icon: string
  category: string
  trigger?: Record<string, unknown>
  capabilities: Array<{
    name: string
    description?: string
  }>
  config: {
    intensity: string[]
    default: string
    preserve_original: boolean
  }
  scope?: 'system' | 'author' | 'project' | string
  version_id?: number
  status?: 'draft' | 'published' | 'retired' | 'unpublished' | string
  execution_mode?: 'transform' | 'policy' | string
  version_snapshot?: SkillVersion
  metrics?: SkillMetrics
  project_id?: string
  base_skill_id?: number
  base_version_id?: number
  is_project_copy?: boolean
}

export interface SkillVersion {
  id: number
  version_number: number
  version_label: string
  status: string
  phase: string
  rules: string[]
  prohibitions: string[]
  checker_keys: string[]
  retrieval_hints: string[]
  prompt_hints: string[]
  verify_hints: string[]
  change_note?: string
  source?: string
  parent_version_id?: number
  created_at?: string
  published_at?: string
}

export interface SkillMetrics {
  usage_count: number
  accepted_count?: number
  acceptance_rate?: number | null
  changed_rate?: number | null
  avg_before_score?: number | null
  avg_after_score?: number | null
}

export interface SkillExecuteRequest {
  project_id: string
  chapter_number: number
  content: string
  chapter_info?: Record<string, unknown>
  character_profiles?: Record<string, unknown>[]
  world_settings?: Record<string, unknown>
  previous_summary?: string
  outline?: Record<string, unknown>
  capability_name?: string
  params?: Record<string, unknown>
  user_id?: number
}

export interface SkillExecuteResponse {
  skill_id: string
  capability_name: string
  original_content: string
  transformed_content: string
  success: boolean
  error?: string
  metadata: Record<string, unknown> & { usage_id?: number }
  changed: boolean
}

export async function listSkills(category?: string): Promise<SkillInfo[]> {
  const params = category ? `?category=${encodeURIComponent(category)}` : ''
  const res = await http.get(`/api/skills${params}`)
  return res.data
}

export async function listSkillCatalog(projectId?: string): Promise<SkillInfo[]> {
  const params = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
  const res = await http.get(`/api/skills/catalog${params}`)
  return res.data
}

export async function listSkillVersions(skillId: string): Promise<SkillVersion[]> {
  const res = await http.get(`/api/skills/${encodeURIComponent(skillId)}/versions`)
  return res.data.versions
}

export async function createSkillDraft(
  skillId: string,
  payload: Omit<SkillDraftPayload, 'change_note'> & { change_note?: string }
): Promise<SkillVersion> {
  const res = await http.post(`/api/skills/${encodeURIComponent(skillId)}/improvement-draft`, payload)
  return res.data
}

export async function publishSkillVersion(skillId: string, versionId: number): Promise<SkillVersion> {
  const res = await http.post(`/api/skills/${encodeURIComponent(skillId)}/publish`, { version_id: versionId })
  return res.data
}

export async function rollbackSkillVersion(skillId: string, versionId: number): Promise<SkillVersion> {
  const res = await http.post(`/api/skills/${encodeURIComponent(skillId)}/rollback`, { version_id: versionId })
  return res.data
}

export async function updateSkillUsageFeedback(
  usageId: number,
  payload: { accepted: boolean; after_score?: number; feedback?: string }
): Promise<{ id: number; accepted: boolean; after_score?: number; feedback?: string }> {
  const res = await http.post(`/api/skills/usages/${usageId}/feedback`, payload)
  return res.data
}

export interface SkillDraftPayload {
  phase: string
  rules: string[]
  prohibitions: string[]
  checker_keys: string[]
  retrieval_hints: string[]
  prompt_hints: string[]
  verify_hints: string[]
  change_note?: string
}

export interface SkillForkPayload extends SkillDraftPayload {
  project_id: string
  name?: string
  description?: string
}

export async function createProjectSkillCopy(
  skillId: string,
  payload: SkillForkPayload
): Promise<{ id: string; version_snapshot?: SkillVersion; base_skill_id?: number; base_version_id?: number }> {
  const res = await http.post(`/api/skills/${encodeURIComponent(skillId)}/project-copy`, payload)
  return res.data
}

export async function getSkillCategories(): Promise<string[]> {
  const res = await http.get('/api/skills/categories')
  return res.data.categories
}

export async function getSkill(skillId: string): Promise<SkillInfo> {
  const res = await http.get(`/api/skills/${skillId}`)
  return res.data
}

export async function executeSkill(
  skillId: string,
  request: SkillExecuteRequest
): Promise<SkillExecuteResponse> {
  const res = await http.post(`/api/skills/${skillId}/execute`, request)
  return res.data
}
