import { describe, expect, it, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'

const listChannels = vi.fn()
vi.mock('@/api/payment', () => ({
  paymentApi: { listChannels: (...args: unknown[]) => listChannels(...args) },
}))

import { usePaymentChannels, FALLBACK_PAYMENT_CHANNELS } from './usePaymentChannels'

describe('usePaymentChannels', () => {
  beforeEach(() => {
    listChannels.mockReset()
  })

  it('selects the first enabled channel and ignores disabled ones', async () => {
    listChannels.mockResolvedValue([
      { channel: 'wechat', label: '微信支付' },
      { channel: 'alipay', label: '支付宝' },
    ])
    const pc = usePaymentChannels()
    await pc.load()
    await nextTick()
    expect(pc.selected.value).toBe('wechat')
    expect(pc.noneEnabled.value).toBe(false)
    pc.select('stripe')
    expect(pc.selected.value).toBe('wechat')
    pc.select('alipay')
    expect(pc.selected.value).toBe('alipay')
  })

  it('reports noneEnabled when the backend returns an empty list', async () => {
    listChannels.mockResolvedValue([])
    const pc = usePaymentChannels()
    await pc.load()
    await nextTick()
    expect(pc.selected.value).toBeNull()
    expect(pc.noneEnabled.value).toBe(true)
    expect(pc.degraded.value).toBe(false)
  })

  it('falls back to the static list when the request fails', async () => {
    listChannels.mockRejectedValue(new Error('network'))
    const pc = usePaymentChannels()
    await pc.load()
    await nextTick()
    expect(pc.channels.value).toEqual(FALLBACK_PAYMENT_CHANNELS)
    expect(pc.selected.value).toBe('stripe')
    expect(pc.degraded.value).toBe(true)
    expect(pc.noneEnabled.value).toBe(false)
  })
})
