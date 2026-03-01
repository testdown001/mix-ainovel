// AIMETA P=LLM_API客户端_模型配置接口|R=LLM配置CRUD|NR=不含UI逻辑|E=api:llm|X=internal|A=llmApi对象|D=axios|S=net|RD=./README.ai
import { requestJson } from './http'

const API_PREFIX = '/api'
const LLM_BASE = `${API_PREFIX}/llm-config`

export interface LLMConfig {
  user_id: number
  llm_provider_url: string | null
  llm_provider_api_key: string | null
  llm_provider_model: string | null
  llm_provider_api_format: string | null
}

export interface LLMConfigCreate {
  llm_provider_url?: string
  llm_provider_api_key?: string
  llm_provider_model?: string
  llm_provider_api_format?: string
}

export const getLLMConfig = async (): Promise<LLMConfig | null> => {
  return requestJson<LLMConfig | null>(LLM_BASE, {
    method: 'GET',
    notFoundValue: null,
    errorMessage: 'Failed to fetch LLM config'
  })
}

export const createOrUpdateLLMConfig = async (config: LLMConfigCreate): Promise<LLMConfig> => {
  return requestJson<LLMConfig>(LLM_BASE, {
    method: 'PUT',
    body: JSON.stringify(config),
    errorMessage: 'Failed to save LLM config'
  })
}

export const deleteLLMConfig = async (): Promise<void> => {
  await requestJson<void>(LLM_BASE, {
    method: 'DELETE',
    errorMessage: 'Failed to delete LLM config'
  })
}

export interface ModelListRequest {
  llm_provider_url?: string
  llm_provider_api_key: string
}

export const getAvailableModels = async (request: ModelListRequest): Promise<string[]> => {
  return requestJson<string[]>(`${LLM_BASE}/models`, {
    method: 'POST',
    body: JSON.stringify(request),
    errorFallbackValue: []
  })
}
