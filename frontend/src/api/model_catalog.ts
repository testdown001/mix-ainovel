// AIMETA P=模型目录API客户端_前台可用模型+后台CRUD|R=/api/model-catalog|E=ModelCatalogAPI|X=internal|A=api对象|D=fetch|S=net
import { requestJson } from './http'

const BASE = '/api/model-catalog'

export interface AvailableModel {
  code: string
  display_name: string
  description?: string | null
  credit_price: number
  min_tier: string
  locked: boolean
}

export interface ModelAvailableResponse {
  tier: string
  credit: {
    balance?: number
    purchased?: number
    total?: number
    monthly_grant?: number
    carryover?: boolean
    reset_at?: string | null
  }
  polish_price: number
  models: AvailableModel[]
}

export interface ModelCatalogItem {
  id: number
  code: string
  display_name: string
  description?: string | null
  real_model?: string | null
  base_url?: string | null
  api_key_ref?: string | null
  api_format?: string | null
  reasoning_effort?: string | null
  credit_price: number
  min_tier: string
  is_active: boolean
  sort_order: number
}

export type ModelCatalogPayload = Omit<ModelCatalogItem, 'id'>

export class ModelCatalogAPI {
  /** 前台：当前档位可用模型(locked 标记) + 我的积分 + 润色单价。实时拉取。 */
  static getAvailable(): Promise<ModelAvailableResponse> {
    return requestJson<ModelAvailableResponse>(`${BASE}/available`)
  }

  // —— 后台 CRUD ——
  static list(): Promise<ModelCatalogItem[]> {
    return requestJson<ModelCatalogItem[]>(`${BASE}/`)
  }
  static create(payload: ModelCatalogPayload): Promise<ModelCatalogItem> {
    return requestJson<ModelCatalogItem>(`${BASE}/`, { method: 'POST', body: JSON.stringify(payload) })
  }
  static update(id: number, payload: ModelCatalogPayload): Promise<ModelCatalogItem> {
    return requestJson<ModelCatalogItem>(`${BASE}/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  }
  static toggle(id: number): Promise<{ id: number; is_active: boolean }> {
    return requestJson(`${BASE}/${id}/toggle`, { method: 'PATCH' })
  }
  static remove(id: number): Promise<void> {
    return requestJson<void>(`${BASE}/${id}`, { method: 'DELETE' })
  }
}
