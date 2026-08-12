import { describe, expect, it } from 'vitest'
import type { Plan } from '@/api/payment'
import { resolvePlanForTier } from './planResolve'

let nextId = 1
const makePlan = (overrides: Partial<Plan>): Plan => ({
  id: nextId++,
  name: '测试套餐',
  price: 29,
  period: 'monthly',
  daily_chapter_limit: 50,
  max_novels: 0,
  is_recommended: false,
  is_active: true,
  tier: 'creator',
  ...overrides,
})

describe('resolvePlanForTier（tier → 可下单套餐解析）', () => {
  it('月付优先于永久与其他周期', () => {
    const monthly = makePlan({ period: 'monthly' })
    const forever = makePlan({ period: 'forever' })
    const yearly = makePlan({ period: 'yearly' })
    expect(resolvePlanForTier([yearly, forever, monthly], 'creator')).toBe(monthly)
  })

  it('过滤未启用套餐：月付停售时回退到永久套餐', () => {
    const inactiveMonthly = makePlan({ period: 'monthly', is_active: false })
    const forever = makePlan({ period: 'forever' })
    expect(resolvePlanForTier([inactiveMonthly, forever], 'creator')).toBe(forever)
  })

  it('无月付/永久时回退到首个生效套餐', () => {
    const yearly = makePlan({ period: 'yearly' })
    expect(resolvePlanForTier([yearly], 'creator')).toBe(yearly)
  })

  it('档位不匹配返回 null', () => {
    const creator = makePlan({ tier: 'creator' })
    expect(resolvePlanForTier([creator], 'flagship')).toBeNull()
  })

  it('空列表返回 null', () => {
    expect(resolvePlanForTier([], 'creator')).toBeNull()
  })
})
