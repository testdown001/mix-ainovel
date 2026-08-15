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

export interface ConstitutionPayload {
  core_theme?: string
  genre?: string
  core_conflict?: string
  story_direction?: string
  core_values?: string
  pov_type?: string
  pov_character?: string
  pov_restrictions?: string
  language_style?: string
  overall_tone?: string
  world_type?: string
  power_system?: string
  world_rules?: Record<string, unknown> | string
  forbidden_content?: string[] | string
  [key: string]: unknown
}

export class ProjectAPI {
  static async getConstitution(
    projectId: string,
  ): Promise<{ project_id: string; constitution: ConstitutionPayload | null }> {
    return requestJson(`${PROJECT_PREFIX}/${projectId}/constitution`)
  }

  static async updateConstitution(
    projectId: string,
    payload: ConstitutionPayload,
  ): Promise<{ project_id: string; constitution: ConstitutionPayload }> {
    return requestJson(`${PROJECT_PREFIX}/${projectId}/constitution`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  }

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
