import type { Plan } from '@/api/payment'

/**
 * tier → 可下单套餐解析（月付优先，其次永久，再次任一生效套餐）。
 * PricingView 与 SubscriptionPanel 共用，避免两处漂移导致「下错套餐 / 404」。
 */
export const resolvePlanForTier = (plans: Plan[], tier: string): Plan | null => {
  const cands = plans.filter((p) => p.tier === tier && p.is_active)
  return (
    cands.find((p) => p.period === 'monthly') ||
    cands.find((p) => p.period === 'forever') ||
    cands[0] ||
    null
  )
}
