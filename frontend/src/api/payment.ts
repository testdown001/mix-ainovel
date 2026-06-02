import { http } from './http'

// 后端真实前缀（此前误用 /api/v2，后端根本无此命名空间，导致全部 404）。
// 套餐: plans 路由 prefix=/api/plans；支付: payment 路由 prefix=/api/payment。
const PLANS = '/api/plans'
const PAYMENT = '/api/payment'

export interface PlanCapability {
  key: string
  label: string
  description: string
  min_tier?: string
}

export interface Plan {
  id: number
  name: string
  description?: string
  price: number
  period: string
  daily_chapter_limit: number
  max_novels: number
  tier?: string
  // 后端返回的是字符串数组（营销文案）；capabilities 为该档位解锁的能力（与门控同源）
  features?: string[]
  capabilities?: PlanCapability[]
  is_recommended: boolean
  is_active: boolean
}

export interface PaymentOrder {
  id: number
  order_no: string
  plan_name: string
  amount: number
  channel: string
  status: string
  paid_at?: string | null
  created_at: string | null
}

// 管理员订单视图（比用户视图多 username/currency/transaction_id 等，与后端 list_orders_for_admin 对齐）
export interface AdminPaymentOrder {
  id: number
  order_no: string
  username?: string
  user_id: number
  plan_id: number
  plan_name: string
  amount: number
  currency: string
  channel: string
  status: string
  transaction_id?: string | null
  paid_at?: string | null
  refunded_at?: string | null
  remark?: string | null
  created_at: string | null
}

// 订阅状态由配额(/api/quota/me)推导（系统以配额表达会员状态，无独立订阅表）。
// 多数字段可选，以适配"从配额派生"的最小形态。
export interface Subscription {
  status: string
  plan_tier?: string
  current_period_end?: string | null
  id?: number
  user_id?: number
  plan_id?: number
  current_period_start?: string
  cancelled_at?: string
}

// 与后端 CreateOrderResponse 对齐：{order_no, pay_url, channel, status}
export interface CreateOrderResponse {
  order_no: string
  pay_url?: string
  channel: string
  status: string
}

export const paymentApi = {
  /** 公开套餐列表（后端返回原始数组，无 {success,data} 包裹）。 */
  async listPlans(): Promise<Plan[]> {
    const { data } = await http.get<Plan[]>(`${PLANS}/public`)
    return data
  },

  /**
   * 创建支付订单。后端支持渠道：alipay / wechat / stripe。
   */
  async createOrder(
    planId: number,
    channel: 'alipay' | 'wechat' | 'stripe',
    returnUrl?: string
  ): Promise<CreateOrderResponse> {
    const { data } = await http.post<CreateOrderResponse>(`${PAYMENT}/create-order`, {
      plan_id: planId,
      channel,
      return_url: returnUrl,
    })
    return data
  },

  /**
   * 管理员查询全部支付订单（后端 GET /api/payment/admin/orders）。
   * 支持按渠道/状态过滤；返回原始 {items,total,page,page_size}。
   */
  async adminListOrders(params: {
    channel?: string
    status?: string
    page?: number
    pageSize?: number
  } = {}): Promise<{ items: AdminPaymentOrder[]; total: number; page: number; page_size: number }> {
    const q = new URLSearchParams()
    if (params.channel) q.set('channel', params.channel)
    if (params.status) q.set('status', params.status)
    q.set('page', String(params.page ?? 1))
    q.set('page_size', String(params.pageSize ?? 20))
    const { data } = await http.get<{
      items: AdminPaymentOrder[]
      total: number
      page: number
      page_size: number
    }>(`${PAYMENT}/admin/orders?${q.toString()}`)
    return data
  },

  /** 当前用户支付订单（后端返回原始 {items,total,page,page_size}）。 */
  async listOrders(
    page = 1,
    pageSize = 20
  ): Promise<{ items: PaymentOrder[]; total: number; page?: number; page_size?: number }> {
    const { data } = await http.get<{ items: PaymentOrder[]; total: number }>(
      `${PAYMENT}/orders?page=${page}&page_size=${pageSize}`
    )
    return data
  },

  /**
   * 查询当前订阅 —— 基于配额(/api/quota/me)推导（系统以会员配额表达订阅状态，无独立订阅表）。
   * 非会员返回 null；会员返回 {status:'active', plan_tier, current_period_end=到期时间}。
   */
  async getSubscription(): Promise<Subscription | null> {
    try {
      const { data } = await http.get<{
        is_premium: boolean
        plan_tier?: string
        premium_expires_at?: string | null
      }>('/api/quota/me')
      if (!data?.is_premium) return null
      return {
        status: 'active',
        plan_tier: data.plan_tier,
        current_period_end: data.premium_expires_at ?? null,
      }
    } catch {
      return null
    }
  },
}
