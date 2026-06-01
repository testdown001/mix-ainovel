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

export interface Subscription {
  id: number
  user_id: number
  plan_id: number
  status: string
  current_period_start: string
  current_period_end: string
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
   * 创建支付订单。
   * 注意：后端当前仅支持 channel = 'alipay' | 'wechat'（不支持 'stripe'）。
   * 调用方需传入受支持的渠道，否则后端返回 400。
   */
  async createOrder(
    planId: number,
    channel: 'alipay' | 'wechat',
    returnUrl?: string
  ): Promise<CreateOrderResponse> {
    const { data } = await http.post<CreateOrderResponse>(`${PAYMENT}/create-order`, {
      plan_id: planId,
      channel,
      return_url: returnUrl,
    })
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
   * 查询当前订阅。
   * ⚠️ 后端暂未实现订阅(subscription)端点（仅有订单/配额）。此处优雅降级返回 null，
   * 避免请求不存在的路由报错。如需"当前订阅"展示，应先在后端补订阅端点，
   * 或改为基于 /api/quota 的会员状态(plan_tier/premium_expires_at)推导。
   */
  async getSubscription(): Promise<Subscription | null> {
    return null
  },

  /**
   * 取消订阅。
   * ⚠️ 同上，后端暂无订阅取消端点。保留接口占位，调用即抛出明确提示，避免静默失败。
   */
  async cancelSubscription(): Promise<void> {
    throw new Error('订阅取消功能尚未在后端实现，请联系管理员或通过工单处理。')
  },
}
