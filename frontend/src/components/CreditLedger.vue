<!-- AIMETA P=积分流水明细页|R=展示当前用户积分余额+流水分页|NR=不含扣费逻辑|E=component:CreditLedger|X=ui|A=面板|D=vue,credits-api|S=net -->
<template>
  <div class="credit-ledger">
    <!-- 余额概览 -->
    <div class="rounded-xl p-5 mb-5" style="background:#141414; border:1px solid #2A2A2A;">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div class="text-xs" style="color:#888;">当前积分余额</div>
          <div class="text-3xl font-bold mt-1" style="color:#FFE500; font-family:'Space Grotesk',sans-serif;">
            🪙 {{ (balance ?? 0).toLocaleString() }}
          </div>
        </div>
        <div class="text-right text-xs" style="color:#888;">
          <div v-if="monthlyGrant != null">每月发放 <span style="color:#ccc;">{{ monthlyGrant.toLocaleString() }}</span></div>
          <div v-if="resetAt" class="mt-1">下次重置 <span style="color:#ccc;">{{ formatDate(resetAt) }}</span></div>
        </div>
      </div>
      <div class="text-[11px] mt-3" style="color:#666;">
        锚点：1 篇标准章（章鱼2.0）= 10 积分；润色每章 +5。月度池默认不累积。
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
        <div class="text-3xl mb-2">🪙</div>
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
import { creditsApi, type CreditLogItem } from '@/api/credits'
import { ModelCatalogAPI } from '@/api/model_catalog'

const limit = 20
const offset = ref(0)
const total = ref(0)
const items = ref<CreditLogItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const balance = ref<number | null>(null)
const monthlyGrant = ref<number | null>(null)
const resetAt = ref<string | null>(null)

const page = computed(() => Math.floor(offset.value / limit) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

const reasonLabelMap: Record<string, string> = {
  generate: '章节生成',
  polish: '润色加成',
  refund: '失败退款',
  grant: '额度发放',
  admin: '管理员调整',
}
const reasonLabel = (r: string) => reasonLabelMap[r] || r
const reasonColorMap: Record<string, string> = {
  generate: '#C084FC',
  polish: '#FFB020',
  refund: '#2ED573',
  grant: '#3B82F6',
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
const formatDate = (s?: string | null) => {
  if (!s) return '—'
  const d = new Date(s)
  if (isNaN(d.getTime())) return s
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

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
