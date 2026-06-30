// AIMETA P=积分流水API客户端|R=/api/quota/me/credit-logs|E=creditsApi|X=internal|A=api对象|D=fetch|S=net
import { requestJson } from './http'

export interface CreditLogItem {
  id: number
  delta: number
  reason: string
  ref_key?: string | null
  balance_after: number
  note?: string | null
  created_at?: string | null
}

export interface CreditLogPage {
  items: CreditLogItem[]
  total: number
  limit: number
  offset: number
}

export const creditsApi = {
  /** 当前用户积分流水（分页，时间倒序）。 */
  listLogs: (limit = 20, offset = 0) =>
    requestJson<CreditLogPage>(`/api/quota/me/credit-logs?limit=${limit}&offset=${offset}`),
}
