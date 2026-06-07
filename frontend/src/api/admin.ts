// AIMETA P=管理员API客户端_管理接口调用|R=用户管理_系统配置_统计|NR=不含UI逻辑|E=api:admin|X=internal|A=adminApi对象|D=axios|S=net|RD=./README.ai
import type { NovelSectionResponse, NovelSectionType } from '@/api/novel'
import { requestJson } from './http'

// API 配置
export const API_BASE_URL = ''
export const ADMIN_API_PREFIX = '/api/admin'

const adminRequest = <T = any>(path: string, options: RequestInit = {}) =>
  requestJson<T>(`${API_BASE_URL}${ADMIN_API_PREFIX}${path}`, options)

// 类型定义
export type ChannelType = 'default' | 'fallback' | 'polish' | 'search' | 'embedding'

export interface TestChannelResult {
  ok: boolean
  model: string
  latency_ms: number
  detail: string
}

export interface ApiUsageRow {
  log_date: string
  model: string
  api_type: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  request_count: number
}

export interface ApiUsageStats {
  period: string
  start_date: string
  end_date: string
  rows: ApiUsageRow[]
  summary: Array<{
    model: string
    api_type: string
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    request_count: number
  }>
  grand_total_tokens: number
  grand_total_requests: number
}

export interface Statistics {
  novel_count: number
  user_count: number
  api_request_count: number
}

export interface AdminUser {
  id: number
  username: string
  email?: string | null
  is_admin: boolean
  is_active: boolean
  plan_tier?: string | null
  effective_tier?: string | null
  current_plan_name?: string | null
  premium_expires_at?: string | null
}

export interface AdminUserQuotaSummary {
  is_premium: boolean
  plan_tier: string
  effective_tier: string
  premium_expires_at?: string | null
  daily_chapter_limit: number
  daily_chapter_used: number
  monthly_token_limit: number
  monthly_token_used: number
  storage_limit: number
  storage_used: number
}

export interface AdminPlanSummary {
  id: number
  name: string
  description?: string | null
  price: number
  period: string
  tier: string
  daily_chapter_limit: number
  max_novels: number
  is_active: boolean
}

export interface AdminUserSubscriptionHistoryItem {
  id: number
  order_no: string
  plan_id: number
  plan_name: string
  amount: number
  currency: string
  channel: string
  status: string
  paid_at?: string | null
  created_at?: string | null
  remark?: string | null
}

export interface AdminUserSubscriptionDetail {
  user: AdminUser
  quota: AdminUserQuotaSummary
  current_plan?: AdminPlanSummary | null
  plans: AdminPlanSummary[]
  history: AdminUserSubscriptionHistoryItem[]
}

export interface AssignSubscriptionPayload {
  plan_id: number
  period: 'monthly' | 'yearly'
  remark?: string | null
}

export interface UserCreatePayload {
  username: string
  email?: string
  password: string
  is_admin?: boolean
  is_active?: boolean
}

export interface UserUpdatePayload {
  username?: string
  email?: string
  password?: string
  is_admin?: boolean
  is_active?: boolean
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}

export interface AdminNovelSummary extends NovelProjectSummary {
  owner_id: number
  owner_username: string
}

export interface Chapter {
  chapter_number: number
  title: string
  summary: string
  content?: string | null
  status?: string
  version_id?: string | number | null
  versions?: any[]
  word_count?: number
}

export interface NovelProject {
  id: string
  user_id: number
  title: string
  initial_prompt: string
  conversation_history: any[]
  blueprint?: any
  chapters: Chapter[]
}

export interface PromptItem {
  id: number
  name: string
  title?: string | null
  content: string
  tags?: string[] | null
}

export interface PromptCreatePayload {
  name: string
  content: string
  title?: string
  tags?: string[]
}

export type PromptUpdatePayload = Partial<Omit<PromptCreatePayload, 'name'>>

export interface UpdateLog {
  id: number
  content: string
  created_at: string
  created_by?: string | null
  is_pinned: boolean
}

export interface UpdateLogPayload {
  content?: string
  is_pinned?: boolean
}

export interface DailyRequestLimit {
  limit: number
}

export interface SystemConfig {
  key: string
  value: string
  description?: string | null
}

export interface SystemConfigUpsertPayload {
  value: string
  description?: string | null
}

export type SystemConfigUpdatePayload = Partial<SystemConfigUpsertPayload>

export class AdminAPI {
  private static request<T = any>(path: string, options: RequestInit = {}) {
    return adminRequest<T>(path, options)
  }

  // Overview
  static getStatistics(): Promise<Statistics> {
    return this.request('/stats')
  }

  // Users
  static listUsers(): Promise<AdminUser[]> {
    return this.request('/users')
  }

  static createUser(payload: UserCreatePayload): Promise<AdminUser> {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static getUser(id: number): Promise<AdminUser> {
    return this.request(`/users/${id}`)
  }

  static getUserSubscription(id: number): Promise<AdminUserSubscriptionDetail> {
    return this.request(`/users/${id}/subscription`)
  }

  static assignUserSubscription(
    id: number,
    payload: AssignSubscriptionPayload
  ): Promise<AdminUserSubscriptionDetail> {
    return this.request(`/users/${id}/subscription`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static updateUser(id: number, payload: UserUpdatePayload): Promise<AdminUser> {
    return this.request(`/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteUser(id: number): Promise<void> {
    return this.request(`/users/${id}`, {
      method: 'DELETE'
    })
  }

  // Novels
  static listNovels(): Promise<AdminNovelSummary[]> {
    return this.request('/novel-projects')
  }

  static getNovelDetails(projectId: string): Promise<NovelProject> {
    return this.request(`/novel-projects/${projectId}`)
  }

  static getNovelSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return this.request(`/novel-projects/${projectId}/sections/${section}`)
  }

  static getNovelChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return this.request(`/novel-projects/${projectId}/chapters/${chapterNumber}`)
  }

  // Prompts
  static listPrompts(): Promise<PromptItem[]> {
    return this.request('/prompts')
  }

  static createPrompt(payload: PromptCreatePayload): Promise<PromptItem> {
    return this.request('/prompts', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static getPrompt(id: number): Promise<PromptItem> {
    return this.request(`/prompts/${id}`)
  }

  static updatePrompt(id: number, payload: PromptUpdatePayload): Promise<PromptItem> {
    return this.request(`/prompts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deletePrompt(id: number): Promise<void> {
    return this.request(`/prompts/${id}`, {
      method: 'DELETE'
    })
  }

  // Update logs
  static listUpdateLogs(): Promise<UpdateLog[]> {
    return this.request('/update-logs')
  }

  static createUpdateLog(payload: UpdateLogPayload & { content: string }): Promise<UpdateLog> {
    return this.request('/update-logs', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static updateUpdateLog(id: number, payload: UpdateLogPayload): Promise<UpdateLog> {
    return this.request(`/update-logs/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteUpdateLog(id: number): Promise<void> {
    return this.request(`/update-logs/${id}`, {
      method: 'DELETE'
    })
  }

  // Settings
  static getDailyRequestLimit(): Promise<DailyRequestLimit> {
    return this.request('/settings/daily-request-limit')
  }

  static setDailyRequestLimit(limit: number): Promise<DailyRequestLimit> {
    return this.request('/settings/daily-request-limit', {
      method: 'PUT',
      body: JSON.stringify({ limit })
    })
  }

  static listSystemConfigs(): Promise<SystemConfig[]> {
    return this.request('/system-configs')
  }

  static upsertSystemConfig(key: string, payload: SystemConfigUpsertPayload): Promise<SystemConfig> {
    return this.request(`/system-configs/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ key, ...payload })
    })
  }

  static patchSystemConfig(key: string, payload: SystemConfigUpdatePayload): Promise<SystemConfig> {
    return this.request(`/system-configs/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteSystemConfig(key: string): Promise<void> {
    return this.request(`/system-configs/${key}`, {
      method: 'DELETE'
    })
  }

  static changePassword(oldPassword: string, newPassword: string): Promise<void> {
    return this.request('/password', {
      method: 'POST',
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword
      })
    })
  }

  /** 真实检测某个 LLM/embedding 通道是否可用（发起一次最小调用）。 */
  static testLlmChannel(channelType: ChannelType): Promise<TestChannelResult> {
    return this.request('/test-llm-channel', {
      method: 'POST',
      body: JSON.stringify({ channel_type: channelType })
    })
  }

  /** API 用量统计（注意：走 /api/api-usage，而非 /api/admin）。 */
  static getApiUsageStats(params: {
    period: 'day' | 'week' | 'month' | 'custom'
    startDate?: string
    endDate?: string
  }): Promise<ApiUsageStats> {
    const q = new URLSearchParams({ period: params.period })
    if (params.period === 'custom' && params.startDate && params.endDate) {
      q.set('start_date', params.startDate)
      q.set('end_date', params.endDate)
    }
    return requestJson<ApiUsageStats>(`/api/api-usage/stats?${q.toString()}`)
  }
}
