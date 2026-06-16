import { describe, it, expect, vi, beforeEach } from 'vitest'

// mock http 出口（vi.mock 会被提升到 import 之前执行）
vi.mock('./http', () => ({
  http: { get: vi.fn(), post: vi.fn() },
}))

import { paymentApi } from './payment'
import { http } from './http'

const mockedGet = vi.mocked(http.get)

describe('paymentApi.getSubscription（订阅状态由 /api/quota/me 推导，无独立订阅表）', () => {
  beforeEach(() => {
    mockedGet.mockReset()
  })

  it('非会员(is_premium=false) 返回 null', async () => {
    mockedGet.mockResolvedValue({ data: { is_premium: false } } as never)
    expect(await paymentApi.getSubscription()).toBeNull()
  })

  it('会员返回 active + plan_tier + 到期时间', async () => {
    mockedGet.mockResolvedValue({
      data: { is_premium: true, plan_tier: 'creator', premium_expires_at: '2026-12-31T00:00:00Z' },
    } as never)
    expect(await paymentApi.getSubscription()).toEqual({
      status: 'active',
      plan_tier: 'creator',
      current_period_end: '2026-12-31T00:00:00Z',
    })
  })

  it('会员但缺 premium_expires_at 时 current_period_end 为 null', async () => {
    mockedGet.mockResolvedValue({ data: { is_premium: true, plan_tier: 'flagship' } } as never)
    const sub = await paymentApi.getSubscription()
    expect(sub?.current_period_end).toBeNull()
    expect(sub?.plan_tier).toBe('flagship')
  })

  it('请求异常时容错返回 null（不抛出）', async () => {
    mockedGet.mockRejectedValue(new Error('network'))
    expect(await paymentApi.getSubscription()).toBeNull()
  })
})
