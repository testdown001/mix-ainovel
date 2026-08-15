<!-- AIMETA P=积分流水明细页|R=展示当前用户积分余额+流水分页|NR=不含扣费逻辑|E=component:CreditLedger|X=ui|A=面板|D=vue,credits-api|S=net -->
<template>
  <div class="credit-ledger">
    <!-- 余额概览（双池：月度池随重置清零，永久池为充值所得永不过期） -->
    <div class="rounded-xl p-5 mb-5" style="background:#141414; border:1px solid #2A2A2A;">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div class="text-xs" style="color:#888;">当前可用积分</div>
          <div class="text-3xl font-bold mt-1 flex items-center gap-2"
            style="color:#FFE500; font-family:'Space Grotesk',sans-serif;">
            <CoinIcon :size="24" /> {{ totalCredits.toLocaleString() }}
          </div>
          <div class="text-[11px] mt-1.5" style="color:#888;">
            月度池 <span style="color:#ccc;">{{ (balance ?? 0).toLocaleString() }}</span>
            <span class="mx-1.5" style="color:#444;">·</span>
            永久池 <span style="color:#2ED573;">{{ (purchased ?? 0).toLocaleString() }}</span>
            <span class="ml-1" style="color:#555;">(充值所得,不过期)</span>
          </div>
        </div>
        <div class="text-right text-xs" style="color:#888;">
          <div v-if="monthlyGrant != null">每月发放 <span style="color:#ccc;">{{ monthlyGrant.toLocaleString() }}</span></div>
          <div v-if="nextResetLabel" class="mt-1">下次重置 <span style="color:#ccc;">{{ nextResetLabel }}</span></div>
        </div>
      </div>
      <div class="text-[11px] mt-3" style="color:#666;">
        锚点：1 篇标准章（章鱼2.0）= 10 积分；润色每章 +5；蓝图深度打磨默认 20（后台可改）。消费先扣月度池，再扣永久池。
      </div>
    </div>

    <!-- 积分加油包 -->
    <div class="rounded-xl p-5 mb-5" style="background:#141414; border:1px solid #2A2A2A;">
      <div class="flex items-center justify-between mb-1">
        <span class="text-sm font-semibold text-white">积分加油包</span>
        <div class="flex items-center gap-1.5">
          <button v-for="ch in channelOptions" :key="ch.value" @click="packChannel = ch.value"
            class="px-2.5 py-0.5 rounded-full text-[11px] transition-colors"
            :style="packChannel === ch.value
              ? 'background:#FFE500;color:#000;font-weight:600;'
              : 'background:#1A1A1A;border:1px solid #2A2A2A;color:#888;'">
            {{ ch.label }}
          </button>
        </div>
      </div>
      <div class="text-[11px] mb-3" style="color:#666;">充值积分入永久池，永不过期；支付完成后点「刷新」查看到账。</div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div v-for="pack in packs" :key="pack.code"
          class="rounded-lg p-4 flex flex-col gap-2"
          style="background:#0F0F0F; border:1px solid #2A2A2A;">
          <div class="text-xs" style="color:#888;">{{ pack.name }}</div>
          <div class="text-xl font-bold" style="color:#FFE500; font-family:'Space Grotesk',sans-serif;">
            {{ pack.credits.toLocaleString() }} <span class="text-xs font-normal" style="color:#888;">积分</span>
          </div>
          <button @click="buyPack(pack)"
            :disabled="buyingCode === pack.code"
            class="mt-1 w-full py-2 rounded-lg text-xs font-semibold transition-colors"
            style="background:#FFE500;color:#000;">
            {{ buyingCode === pack.code ? '创建订单中…' : `¥${pack.price} 购买` }}
          </button>
        </div>
      </div>
      <div v-if="packError" class="text-xs mt-3" style="color:#E5484D;">{{ packError }}</div>
      <div v-if="packPayUrl" class="text-xs mt-3" style="color:#888;">
        已在新窗口打开支付页；如未打开请
        <a :href="packPayUrl" target="_blank" style="color:#FFE500;">点此前往支付</a>。
      </div>
    </div>

    <!-- 流水表 -->
    <div class="rounded-xl overflow-hidden" style="background:#141414; border:1px solid #2A2A2A;">
      <div class="flex items-center justify-between px-5 py-3" style="border-bottom:1px solid #2A2A2A;">
        <span class="text-sm font-semibold text-white">积分流水</span>
        <button class="text-xs px-2.5 py-1 rounded-md" style="color:#888; border:1px solid #2A2A2A;"
          :disabled="loading" @click="reload">刷新</button>
      </div>

      <div v-if="loading" class="py-16 text-center text-sm" style="color:#666;">加载中…</div>
      <div v-else-if="error" class="py-16 text-center text-sm" style="color:#E5484D;">{{ error }}</div>
      <div v-else-if="items.length === 0" class="py-16 text-center" style="color:#666;">
        <CoinIcon :size="28" class="mx-auto mb-2" style="color:#444;" />
        <div class="text-sm">暂无积分流水</div>
      </div>

      <div v-else class="ledger-rows">
        <div v-for="row in items" :key="row.id" class="ledger-row">
          <div class="flex items-center gap-3 min-w-0">
            <span class="reason-tag" :style="reasonStyle(row.reason)">{{ reasonLabel(row.reason) }}</span>
            <div class="min-w-0">
              <div class="text-xs truncate" style="color:#ccc;">{{ row.note || refDisplay(row) }}</div>
              <div class="text-[11px]" style="color:#666;">{{ formatDateTime(row.created_at) }}</div>
            </div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-sm font-bold" :style="{ color: row.delta >= 0 ? '#2ED573' : '#E5484D' }">
              {{ row.delta >= 0 ? '+' : '' }}{{ row.delta.toLocaleString() }}
            </div>
            <div class="text-[11px]" style="color:#666;">余 {{ row.balance_after.toLocaleString() }}</div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="!loading && total > limit" class="flex items-center justify-between px-5 py-3"
        style="border-top:1px solid #2A2A2A;">
        <span class="text-[11px]" style="color:#666;">共 {{ total }} 条 · 第 {{ page }}/{{ totalPages }} 页</span>
        <div class="flex gap-2">
          <button class="pager-btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
          <button class="pager-btn" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import CoinIcon from '@/components/shared/CoinIcon.vue'
import { creditsApi, type CreditLogItem } from '@/api/credits'
import { ModelCatalogAPI } from '@/api/model_catalog'
import { paymentApi, type CreditPack } from '@/api/payment'

const limit = 20
const offset = ref(0)
const total = ref(0)
const items = ref<CreditLogItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const balance = ref<number | null>(null)
const purchased = ref<number | null>(null)
const monthlyGrant = ref<number | null>(null)
const resetAt = ref<string | null>(null)
const totalCredits = computed(() => (balance.value ?? 0) + (purchased.value ?? 0))

// 加油包购买
const packs = ref<CreditPack[]>([])
const packChannel = ref<'alipay' | 'wechat' | 'stripe'>('alipay')
const channelOptions: { value: 'alipay' | 'wechat' | 'stripe'; label: string }[] = [
  { value: 'alipay', label: '支付宝' },
  { value: 'wechat', label: '微信' },
  { value: 'stripe', label: 'Stripe' },
]
const buyingCode = ref<string | null>(null)
const packError = ref('')
const packPayUrl = ref('')

const fetchPacks = async () => {
  try {
    packs.value = await paymentApi.listCreditPacks()
  } catch {
    // 目录拉取失败不阻塞页面
  }
}

const buyPack = async (pack: CreditPack) => {
  buyingCode.value = pack.code
  packError.value = ''
  packPayUrl.value = ''
  try {
    const result = await paymentApi.createCreditOrder(pack.code, packChannel.value)
    if (result.pay_url) {
      packPayUrl.value = result.pay_url
      window.open(result.pay_url, '_blank')
    } else {
      packError.value = '未获取到支付链接，请换一个支付方式重试'
    }
  } catch (err: any) {
    packError.value = err?.message || '创建订单失败，请稍后重试'
  } finally {
    buyingCode.value = null
  }
}

const page = computed(() => Math.floor(offset.value / limit) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

const reasonLabelMap: Record<string, string> = {
  generate: '章节生成',
  blueprint_deep: '蓝图深度打磨',
  polish: '润色加成',
  // 退款不只发生在整单失败：润色等付费项没兑现时也会按项退回，标签保持中性，
  // 具体原因由每行的 note 说明（「生成失败/取消退款」「润色未交付退款」）
  refund: '退款',
  grant: '额度发放',
  topup: '积分充值',
  trial: '注册礼',
  admin: '管理员调整',
}
const reasonLabel = (r: string) => reasonLabelMap[r] || r
const reasonColorMap: Record<string, string> = {
  generate: '#C084FC',
  blueprint_deep: '#60A5FA',
  polish: '#FFB020',
  refund: '#2ED573',
  grant: '#3B82F6',
  topup: '#FFE500',
  trial: '#2ED573',
  admin: '#888888',
}
const reasonStyle = (r: string) => {
  const c = reasonColorMap[r] || '#888888'
  return { color: c, background: `${c}1A`, border: `1px solid ${c}40` }
}
const refDisplay = (row: CreditLogItem) =>
  row.ref_key ? `单号 ${row.ref_key.slice(0, 24)}` : '—'

const pad = (n: number) => String(n).padStart(2, '0')
const formatDateTime = (s?: string | null) => {
  if (!s) return '—'
  const d = new Date(s)
  if (isNaN(d.getTime())) return s
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
// 后端返回的 reset_at 是「上次重置锚点」，下次重置 = 锚点 + 30 天（与后端 CREDIT_RESET_DAYS 对齐）。
// 此前直接展示锚点日期，用户会看到一个过去的「下次重置」时间。
const nextResetLabel = computed(() => {
  if (!resetAt.value) return null
  const d = new Date(resetAt.value)
  if (isNaN(d.getTime())) return null
  d.setDate(d.getDate() + 30)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
})

const fetchLogs = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await creditsApi.listLogs(limit, offset.value)
    items.value = res.items || []
    total.value = res.total || 0
  } catch {
    error.value = '加载流水失败'
  } finally {
    loading.value = false
  }
}

const fetchBalance = async () => {
  try {
    const res = await ModelCatalogAPI.getAvailable()
    balance.value = res.credit?.balance ?? 0
    purchased.value = (res.credit as any)?.purchased ?? 0
    monthlyGrant.value = res.credit?.monthly_grant ?? null
    resetAt.value = res.credit?.reset_at ?? null
  } catch {
    // 余额拉取失败不阻塞流水展示
  }
}

const go = (p: number) => {
  const next = Math.min(Math.max(1, p), totalPages.value)
  offset.value = (next - 1) * limit
  fetchLogs()
}
const reload = () => {
  offset.value = 0
  fetchBalance()
  fetchLogs()
}

onMounted(() => {
  fetchBalance()
  fetchLogs()
  fetchPacks()
})
</script>

<style scoped>
.ledger-rows {
  display: flex;
  flex-direction: column;
}
.ledger-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid #1f1f1f;
}
.ledger-row:last-child {
  border-bottom: none;
}
.reason-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
  flex-shrink: 0;
}
.pager-btn {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 6px;
  color: #ccc;
  border: 1px solid #2A2A2A;
  background: transparent;
}
.pager-btn:disabled {
  color: #555;
  cursor: not-allowed;
}
</style>
