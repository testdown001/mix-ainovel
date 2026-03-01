// AIMETA P=写作偏好API客户端_风格配置接口|R=写作偏好CRUD|NR=不含UI逻辑|E=api:writingPreferences|X=internal|A=API对象|D=fetch|S=net|RD=./README.ai
import { requestJson } from './http'

const API_PREFIX = '/api'
const BASE = `${API_PREFIX}/writing-preferences`

export interface WritingPreference {
  user_id: number
  style_preset: string | null
  custom_rules: string | null
  banned_phrases: string[] | null
}

export interface WritingPreferenceCreate {
  style_preset?: string | null
  custom_rules?: string | null
  banned_phrases?: string[] | null
}

export interface PresetInfo {
  key: string
  name: string
  description: string
  banned_phrases: string[]
}

export const getWritingPreference = async (): Promise<WritingPreference | null> => {
  return requestJson<WritingPreference | null>(BASE, {
    method: 'GET',
    notFoundValue: null,
    errorMessage: 'Failed to fetch writing preference'
  })
}

export const saveWritingPreference = async (data: WritingPreferenceCreate): Promise<WritingPreference> => {
  return requestJson<WritingPreference>(BASE, {
    method: 'PUT',
    body: JSON.stringify(data),
    errorMessage: 'Failed to save writing preference'
  })
}

export const deleteWritingPreference = async (): Promise<void> => {
  await requestJson<void>(BASE, {
    method: 'DELETE',
    errorMessage: 'Failed to delete writing preference'
  })
}

export const getPresets = async (): Promise<PresetInfo[]> => {
  return requestJson<PresetInfo[]>(`${BASE}/presets`, {
    method: 'GET',
    errorMessage: 'Failed to fetch presets'
  })
}
