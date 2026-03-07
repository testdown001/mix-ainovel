import { http } from '@/api/http'

export interface SkillInfo {
  id: string
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
  metadata: Record<string, unknown>
  changed: boolean
}

export async function listSkills(category?: string): Promise<SkillInfo[]> {
  const params = category ? `?category=${encodeURIComponent(category)}` : ''
  const res = await http.get(`/api/skills${params}`)
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
