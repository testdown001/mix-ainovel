<!-- AIMETA P=会员到期提醒横幅|R=到期前3天提示+续费直达|NR=不含支付逻辑|E=component:RenewalBanner|X=ui|A=转化组件|D=vue,payment-api|S=net -->
<template>
  <div v-if="visible"
    class="rounded-xl border px-4 py-3 mb-5 flex items-center justify-between gap-3 flex-wrap"
    style="background:linear-gradient(90deg,#1A1600,#141414); border-color:rgba(255,229,0,0.35);">
    <div class="flex items-center gap-2.5 text-sm" style="color:#DDDDDD;">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
        viewBox="0 0 24 24" style="color:#FFE500;">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <span>
        {{ tierLabel }}将于 <span class="font-bold text-white">{{ daysLeftLabel }}</span> 到期，到期后自动降为免费版，月度积分与档位能力同步回落
      </span>
    </div>
    <div class="flex items-center gap-2 flex-shrink-0">
      <router-link to="/settings?tab=subscription"
        class="px-3.5 py-1.5 rounded-lg text-xs font-semibold"
        style="background:#FFE500; color:#000;">
        立即续费
      </router-link>
      <button @click="dismiss" class="text-xs px-2 py-1.5" style="color:#666;">
        今日不再提醒
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { paymentApi } from '@/api/payment'

/** 到期前 N 天开始提醒 */
const REMIND_DAYS = 3

const expiresAt = ref<Date | null>(null)
const planTier = ref<string | undefined>(undefined)
const dismissedToday = ref(false)

const todayKey = () => {
  const d = new Date()
  return `renewal-dismissed:${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

const daysLeft = computed(() => {
  if (!expiresAt.value) return null
  return Math.ceil((expiresAt.value.getTime() - Date.now()) / 86400000)
})

const visible = computed(
  () =>
    !dismissedToday.value &&
    daysLeft.value !== null &&
    daysLeft.value >= 0 &&
    daysLeft.value <= REMIND_DAYS,
)

const daysLeftLabel = computed(() => {
  if (daysLeft.value === null) return ''
  return daysLeft.value <= 0 ? '今天' : `${daysLeft.value} 天后`
})

const tierLabel = computed(() =>
  planTier.value === 'flagship' ? '旗舰版会员' : '创作者版会员',
)

const dismiss = () => {
  localStorage.setItem(todayKey(), '1')
  dismissedToday.value = true
}

onMounted(async () => {
  dismissedToday.value = localStorage.getItem(todayKey()) === '1'
  if (dismissedToday.value) return
  // 订阅状态由配额推导：过期用户 is_premium=false → 返回 null → 横幅不出现
  const sub = await paymentApi.getSubscription()
  if (sub?.current_period_end) {
    expiresAt.value = new Date(sub.current_period_end)
    planTier.value = sub.plan_tier
  }
})
</script>
