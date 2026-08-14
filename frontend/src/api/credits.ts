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

export interface ReferralInfo {
  enabled: boolean
  invite_code: string
  inviter_credits: number
  invitee_credits: number
  max_invites: number
  invited_count: number
  credits_earned: number
}

export const creditsApi = {
  /** 当前用户积分流水（分页，时间倒序）。 */
  listLogs: (limit = 20, offset = 0) =>
    requestJson<CreditLogPage>(`/api/quota/me/credit-logs?limit=${limit}&offset=${offset}`),

  /** 邀请返积分：我的邀请码、奖励规则与统计。 */
  getReferralInfo: () => requestJson<ReferralInfo>('/api/quota/me/referral'),
}
