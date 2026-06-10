// AIMETA P=套餐管理API客户端|R=套餐CRUD_能力注册表|NR=不含UI逻辑|E=plansApi|X=internal|A=对象|D=fetch|S=net|RD=./README.ai
import { requestJson } from './http'

const PLANS_BASE = '/api/plans'

export interface PlanCapability {
  key: string
  label: string
  description: string
  min_tier?: string
  default_min_tier?: string
}

export interface AdminPlan {
  id: number
  name: string
  description?: string | null
  price: number
  period: string
  daily_chapter_limit: number
  max_novels: number
  tier: 'free' | 'creator' | 'flagship'
  features: string[]
  capabilities?: PlanCapability[]
  is_recommended: boolean
  is_active: boolean
  sort_order: number
}

export interface PlanWritePayload {
  name: string
  description?: string | null
  price: number
  period: string
  daily_chapter_limit: number
  max_novels: number
  tier: string
  features: string[]
  is_recommended: boolean
  is_active: boolean
  sort_order: number
}

export const plansApi = {
  /** 公开套餐（含每档解锁的能力）。 */
  listPublic: () => requestJson<AdminPlan[]>(`${PLANS_BASE}/public`),
  /** 全部套餐（管理员）。 */
  listAll: () => requestJson<AdminPlan[]>(`${PLANS_BASE}/`),
  /** 能力注册表 + 受控流水线开关注册表 + 当前生效最低档位（管理员）。 */
  capabilities: () =>
    requestJson<{ capabilities: PlanCapability[]; flow_overrides: PlanCapability[] }>(
      `${PLANS_BASE}/capabilities`,
    ),
  create: (data: PlanWritePayload) =>
    requestJson<AdminPlan>(`${PLANS_BASE}/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: number, data: PlanWritePayload) =>
    requestJson<AdminPlan>(`${PLANS_BASE}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  toggle: (id: number) =>
    requestJson<{ id: number; is_active: boolean }>(`${PLANS_BASE}/${id}/toggle`, {
      method: 'PATCH',
    }),
  remove: (id: number) =>
    requestJson<void>(`${PLANS_BASE}/${id}`, { method: 'DELETE' }),
}
