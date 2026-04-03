// AIMETA P=项目通用API_宪法人格记忆势力等|R=项目配置管理|NR=不含小说生成|E=api:project|X=internal|A=projectApi对象|D=axios|S=net|RD=./README.ai
import { requestJson } from './http'

const PROJECT_PREFIX = '/api/projects'

export interface PersonaPayload {
  id?: number
  name?: string
  description?: string
  style_tags?: string[]
  strengths?: string[]
  weaknesses?: string[]
  preferences?: string[]
  avoidances?: string[]
  sample_sentences?: string[]
  narrative_voice?: string
  language_style?: string
  pacing_style?: string
  emotional_tone?: string
  dialogue_style?: string
  description_style?: string
  show_vs_tell_ratio?: string
  sensory_focus?: string[]
  physiological_reactions?: string[]
  benchmark_texts?: string[]
  personal_quirks?: string[]
  catchphrases?: string[]
  imperfection_patterns?: string[]
  signature_moves?: string[]
  is_active?: boolean
  extra?: Record<string, any>
}

export class ProjectAPI {
  static async getPersona(projectId: string): Promise<{ project_id: string, persona: PersonaPayload | null }> {
    return requestJson(`${PROJECT_PREFIX}/${projectId}/persona`)
  }

  static async updatePersona(projectId: string, payload: PersonaPayload): Promise<{ project_id: string, persona: PersonaPayload }> {
    return requestJson(`${PROJECT_PREFIX}/${projectId}/persona`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  }
}
