import { http } from './http'

const V2 = '/api/v2'

export interface Plan {
  id: number
  name: string
  description?: string
  price: number
  period: string
  daily_chapter_limit: number
  max_novels: number
  features?: string
  is_recommended: boolean
  is_active: boolean
}

export interface PaymentOrder {
  id: number
  user_id: number
  plan_id: number
  amount: number
  currency: string
  status: string
  channel: string
  paid_at?: string
  refunded_at?: string
  created_at: string
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

export interface CreateOrderResponse {
  order_id: number
  checkout_url?: string
  status: string
}

export const paymentApi = {
  async listPlans(): Promise<Plan[]> {
    const { data } = await http.get<{ success: boolean; data: Plan[] }>(`${V2}/plans/public`)
    return data.data
  },

  async createOrder(planId: number, channel = 'stripe', idempotencyKey?: string): Promise<CreateOrderResponse> {
    const { data } = await http.post<{ success: boolean; data: CreateOrderResponse }>(`${V2}/payment/orders`, {
      plan_id: planId,
      channel,
      idempotency_key: idempotencyKey,
    })
    return data.data
  },

  async listOrders(page = 1, pageSize = 20): Promise<{ items: PaymentOrder[]; total: number }> {
    const { data } = await http.get<{ success: boolean; data: { items: PaymentOrder[]; total: number } }>(
      `${V2}/payment/orders?page=${page}&page_size=${pageSize}`
    )
    return data.data
  },

  async getSubscription(): Promise<Subscription | null> {
    const { data } = await http.get<{ success: boolean; data: Subscription | { subscription: null } }>(
      `${V2}/payment/subscription`
    )
    if ('subscription' in data.data && data.data.subscription === null) return null
    return data.data as Subscription
  },

  async cancelSubscription(): Promise<void> {
    await http.post(`${V2}/payment/subscription/cancel`)
  },
}
