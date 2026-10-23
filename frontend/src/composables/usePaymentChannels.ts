import { computed, ref, watch, type Ref } from 'vue'
import { paymentApi, type PaymentChannel, type PaymentChannelInfo } from '@/api/payment'

/**
 * 三处结账（定价页 / 订阅面板 / 加油包）共用的「可用支付方式」。
 *
 * 以前三处各自维护一份静态清单，后台关掉的渠道照样展示，用户点下去才在下单时报
 * 「渠道未启用」。现在以 `GET /api/payment/channels` 为准；接口拉不到时退回完整静态
 * 清单（宁可多显示一个再在下单时报错，也不能把结账按钮全藏掉），并把 `degraded` 置 true。
 * 后台全部关闭时 `channels` 为空，调用方用 `noneEnabled` 显示「暂未开通支付」。
 */
export const FALLBACK_PAYMENT_CHANNELS: PaymentChannelInfo[] = [
  { channel: 'stripe', label: 'Stripe' },
  { channel: 'alipay', label: '支付宝' },
  { channel: 'wechat', label: '微信支付' },
]

export function usePaymentChannels() {
  const channels: Ref<PaymentChannelInfo[]> = ref([])
  const selected = ref<PaymentChannel | null>(null)
  const loaded = ref(false)
  const degraded = ref(false)

  const noneEnabled = computed(() => loaded.value && !degraded.value && channels.value.length === 0)

  // 当前选中的渠道被后台关掉时，自动换到第一个可用渠道；没有可用渠道则清空
  watch(channels, (list) => {
    if (!list.some((c) => c.channel === selected.value)) {
      selected.value = list[0]?.channel ?? null
    }
  })

  const load = async () => {
    try {
      channels.value = await paymentApi.listChannels()
      degraded.value = false
    } catch {
      channels.value = [...FALLBACK_PAYMENT_CHANNELS]
      degraded.value = true
    } finally {
      loaded.value = true
    }
  }

  const select = (channel: PaymentChannel) => {
    if (channels.value.some((c) => c.channel === channel)) selected.value = channel
  }

  return { channels, selected, loaded, degraded, noneEnabled, load, select }
}
