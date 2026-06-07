<!-- AIMETA P=会员套餐_订阅管理|R=套餐展示_升级引导|NR=不含支付逻辑|E=component:SubscriptionPanel|X=ui|A=套餐组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div>
    <!-- Current plan banner -->
    <div class="rounded-xl border p-5 mb-6 flex items-center justify-between gap-4"
      :style="isTrialing
        ? 'background: linear-gradient(135deg,#1A1600 0%,#141414 100%); border-color:#FFE500;'
        : 'background-color:#141414; border-color:#2A2A2A;'">
      <div class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          :style="isTrialing ? 'background:#FFE50020;' : 'background:#1C1C1C;'">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            :style="isTrialing ? 'color:#FFE500;' : 'color:#888888;'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
          </svg>
        </div>
        <div>
          <div v-if="isTrialing" class="flex items-center gap-2 mb-0.5">
            <span class="text-xs font-bold px-2 py-0.5 rounded-full" style="background:#FFE500;color:#000;">试用中</span>
            <span class="text-xs" style="color:#888888;">创作者版完整功能</span>
          </div>
          <div class="font-semibold text-white text-sm">{{ currentPlanName }}</div>
          <div class="text-xs mt-0.5" :style="isTrialing ? 'color:#FFE500;' : 'color:#888888;'">
            {{ isTrialing ? `试用还剩 ${trialDaysLeft} 天，到期自动降为免费版` : '20次AI生成/月 · 1个小说项目' }}
          </div>
        </div>
      </div>
      <div v-if="!isTrialing" class="flex-shrink-0">
        <button @click="scrollToPlans"
          class="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          style="background:#FFE500;color:#000;">
          升级套餐
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 升级收益 -->
    <div class="rounded-xl border p-4 mb-5" style="background:#101010; border-color:#2A2A2A;">
      <div class="text-sm font-bold text-white mb-3">升级后优先解决</div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div v-for="item in upgradeOutcomes" :key="item.title" class="rounded-lg p-3" style="background:#141414;">
          <div class="text-xs font-semibold text-white">{{ item.title }}</div>
          <div class="text-[11px] mt-1 leading-relaxed" style="color:#888;">{{ item.desc }}</div>
        </div>
      </div>
    </div>

    <!-- 支付渠道选择 -->
    <div class="flex items-center gap-2 mb-3">
      <span class="text-xs" style="color:#888;">支付方式</span>
      <button v-for="ch in channelOptions" :key="ch.value"
        @click="selectedChannel = ch.value"
        class="px-3 py-1 rounded-full text-xs transition-colors"
        :style="selectedChannel === ch.value
          ? 'background:#FFE500;color:#000;font-weight:600;'
          : 'background:#1A1A1A;border:1px solid #2A2A2A;color:#888;'">
        {{ ch.label }}
      </button>
    </div>

    <!-- Plans heading -->
    <div class="flex items-center justify-between mb-4" ref="plansRef">
      <h2 class="text-base font-bold text-white">选择套餐</h2>
      <!-- Annual toggle -->
      <div class="flex items-center gap-2.5 px-3 py-1.5 rounded-full border text-xs" style="border-color:#2A2A2A; background:#141414;">
        <span :style="!annual ? 'color:#fff; font-weight:600;' : 'color:#888;'">按月</span>
        <button @click="annual = !annual"
          class="relative w-8 h-4 rounded-full transition-colors flex-shrink-0"
          :style="annual ? 'background:#FFE500;' : 'background:#2A2A2A;'">
          <span class="absolute top-0.5 w-3 h-3 rounded-full transition-all"
            :style="{ left: annual ? 'calc(100% - 14px)' : '2px', background: annual ? '#000' : '#888' }"></span>
        </button>
        <span :style="annual ? 'color:#fff; font-weight:600;' : 'color:#888;'">
          按年
          <span class="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold" style="background:#FFE50015;color:#FFE500;">省20%</span>
        </span>
      </div>
    </div>

    <!-- Plan cards -->
    <div class="grid grid-cols-3 gap-4 mb-8">
      <div v-for="plan in plans" :key="plan.id"
        class="relative rounded-xl flex flex-col transition-all"
        :style="getPlanCardStyle(plan)">

        <!-- Popular badge -->
        <div v-if="plan.badge" class="absolute -top-3 left-0 right-0 flex justify-center">
          <span class="text-[11px] font-bold px-3 py-0.5 rounded-full"
            :style="plan.id === 'creator' ? 'background:#FFE500;color:#000;' : 'background:#7C3AED;color:#fff;'">
            {{ plan.badge }}
          </span>
        </div>

        <div class="p-5 flex flex-col flex-1">
          <!-- Plan icon + name -->
          <div class="flex items-center gap-2.5 mb-4">
            <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              :style="`background:${plan.color}18; border:1px solid ${plan.color}30;`">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                :style="`color:${plan.color};`" v-html="plan.iconPath"></svg>
            </div>
            <div>
              <div class="text-sm font-bold text-white">{{ plan.name }}</div>
              <div class="text-[11px]" style="color:#888888;">{{ plan.desc }}</div>
            </div>
          </div>

          <!-- Price -->
          <div class="mb-4 pb-4 border-b" style="border-color:#2A2A2A;">
            <div class="flex items-baseline gap-1">
              <span class="text-2xl font-bold" :style="plan.price === 0 ? 'color:#888888;' : 'color:#fff;'"
                style="font-family:'Space Grotesk',sans-serif;">
                {{ displayPrice(plan) }}
              </span>
              <span v-if="plan.price > 0" class="text-xs" style="color:#888888;">
                {{ annual ? '/ 月（年付）' : '/ 月' }}
              </span>
            </div>
            <div v-if="plan.price === 0" class="text-xs mt-0.5" style="color:#888888;">永久免费</div>
            <div v-if="plan.price > 0 && annual" class="text-[11px] mt-1" style="color:#888888;">
              即 <span :style="`color:${plan.color};`">¥{{ Math.round(plan.price * 0.8 * 12) }}</span> / 年
            </div>
          </div>

          <!-- Features -->
          <ul class="space-y-2 flex-1 mb-5">
            <li v-for="f in plan.features" :key="f.text" class="flex items-start gap-2 text-xs">
              <div v-if="f.ok" class="w-3.5 h-3.5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                :style="`background:${plan.color}20;`">
                <svg class="w-2 h-2" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"
                  :style="`color:${plan.color};`">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <div v-else class="w-3.5 h-3.5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                style="background:#1C1C1C;">
                <svg class="w-2 h-2" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"
                  style="color:#444;">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </div>
              <span :style="f.ok ? 'color:#CCCCCC;' : 'color:#555555;'">{{ f.text }}</span>
            </li>
          </ul>

          <!-- CTA -->
          <button @click="handleUpgrade(plan)"
            :disabled="plan.id === currentPlan && !isTrialing"
            class="w-full py-2.5 rounded-lg text-sm font-semibold transition-all"
            :style="getCtaStyle(plan)">
            {{ getCtaLabel(plan) }}
          </button>
          <p v-if="plan.id !== 'free'" class="text-center text-[10px] mt-2" style="color:#555;">
            试用期结束自动降为免费版，无需绑卡
          </p>
        </div>
      </div>
    </div>

    <!-- Feature comparison table -->
    <div class="mb-2">
      <h3 class="text-sm font-bold text-white mb-4">详细功能对比</h3>
      <div class="rounded-xl border overflow-hidden" style="border-color:#2A2A2A;">
        <div class="grid grid-cols-4 border-b text-xs" style="background:#141414;border-color:#2A2A2A;">
          <div class="p-3" style="color:#888888;">功能</div>
          <div v-for="plan in plans" :key="plan.id" class="p-3 text-center font-semibold"
            :style="`color:${plan.color === '#888888' ? '#aaa' : plan.color};`">{{ plan.name }}</div>
        </div>
        <div v-for="(row, i) in comparisonRows" :key="i"
          class="grid grid-cols-4 border-b text-xs last:border-b-0"
          :style="i % 2 === 0 ? 'background:#0A0A0A;border-color:#1C1C1C;' : 'background:#141414;border-color:#1C1C1C;'">
          <div class="p-3 flex items-center" style="color:#888888;">{{ row.label }}</div>
          <div v-for="(v, j) in row.vals" :key="j" class="p-3 flex items-center justify-center">
            <svg v-if="v === true" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#2ED573;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
            </svg>
            <svg v-else-if="v === false" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#333333;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
            <span v-else class="text-center font-medium text-white text-[11px]">{{ v }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Checkout redirect dialog -->
    <div v-if="showUpgradeDialog" class="fixed inset-0 z-50 flex items-center justify-center"
      style="background:rgba(0,0,0,0.7);" @click.self="closeDialog">
      <div class="rounded-2xl border p-8 max-w-sm w-full mx-4 text-center"
        style="background:#141414; border-color:#2A2A2A;">
        <div class="w-12 h-12 rounded-xl mx-auto mb-4 flex items-center justify-center" style="background:#FFE50015;">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
          </svg>
        </div>
        <template v-if="checkoutLoading">
          <h3 class="text-lg font-bold text-white mb-2">正在创建订单...</h3>
          <div class="flex justify-center my-4">
            <div class="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style="border-color:#FFE500; border-top-color:transparent;"></div>
          </div>
        </template>
        <template v-else-if="checkoutError">
          <h3 class="text-lg font-bold text-white mb-2">创建订单失败</h3>
          <p class="text-sm mb-6" style="color:#FF6B6B;">{{ checkoutError }}</p>
          <button @click="closeDialog"
            class="w-full py-2.5 rounded-lg font-semibold text-sm"
            style="background:#FFE500;color:#000;">
            关闭
          </button>
        </template>
        <template v-else>
          <h3 class="text-lg font-bold text-white mb-2">即将跳转到支付页面</h3>
          <p class="text-sm mb-6" style="color:#888888;">
            如未自动跳转，请点击下方按钮。
          </p>
          <a v-if="checkoutUrl" :href="checkoutUrl" target="_blank"
            class="block w-full py-2.5 rounded-lg font-semibold text-sm text-center"
            style="background:#FFE500;color:#000;">
            前往支付
          </a>
        </template>
      </div>
    </div>

    <!-- Subscription info（基于会员配额，到期自动降级；后端暂无主动取消端点，故不展示取消按钮）-->
    <div v-if="subscription" class="rounded-xl border p-4 mt-4" style="background:#141414; border-color:#2A2A2A;">
      <div>
        <div class="text-sm font-bold text-white">当前会员</div>
        <div class="text-xs mt-1" style="color:#888;">
          <template v-if="subscription.current_period_end">
            到期时间: {{ new Date(subscription.current_period_end).toLocaleDateString('zh-CN') }}（到期后自动降级为免费版）
          </template>
          <template v-else>长期有效</template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { paymentApi, type Subscription as SubType } from '@/api/payment'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const annual = ref(false)
const showUpgradeDialog = ref(false)
const checkoutLoading = ref(false)
const checkoutError = ref('')
const checkoutUrl = ref('')
const plansRef = ref<HTMLElement | null>(null)
const selectedChannel = ref<'stripe' | 'alipay' | 'wechat'>('stripe')
const channelOptions: { value: 'stripe' | 'alipay' | 'wechat'; label: string }[] = [
  { value: 'stripe', label: 'Stripe' },
  { value: 'alipay', label: '支付宝' },
  { value: 'wechat', label: '微信支付' },
]
const subscription = ref<SubType | null>(null)
const selectedPlanDbId = ref<number | null>(null)

const currentPlan = computed(() => {
  if (subscription.value?.status === 'active') return 'premium'
  return 'free'
})
const isTrialing = computed(() => {
  return authStore.user?.is_premium && !subscription.value
})
const trialDaysLeft = ref(2)
const currentPlanName = computed(() => isTrialing.value ? '创作者版（试用中）' : (currentPlan.value === 'premium' ? '订阅中' : '免费版'))

const scrollToPlans = () => {
  plansRef.value?.scrollIntoView({ behavior: 'smooth' })
}

const upgradeOutcomes = [
  { title: '开局不落俗套', desc: '用缪斯人格、参考作品和跨界素材，快速找到更有记忆点的题材切口。' },
  { title: '长篇更稳', desc: '用标准/精品生成、知识库和章节体检，降低人物跑偏、伏笔遗漏和设定冲突。' },
  { title: '减少返工', desc: '多版本、评审和关键章节精修，让你在定稿前看到风险和替代方案。' },
]

const plans = [
  {
    id: 'free',
    dbId: 0,
    name: '免费版',
    price: 0,
    desc: '体验完整主线',
    color: '#888888',
    badge: null,
    iconPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>',
    features: [
      { text: '1 个小说项目', ok: true },
      { text: '20次基础章节生成 / 月', ok: true },
      { text: '灵感到蓝图主流程', ok: true },
      { text: '基础角色与大纲管理', ok: true },
      { text: '跨界素材与多缪斯开局', ok: false },
      { text: '稳定连载生成模式', ok: false },
      { text: '关键章节精修', ok: false },
    ],
  },
  {
    id: 'creator',
    dbId: 2,
    name: '创作者版',
    price: 29,
    desc: '稳定连载的首选',
    color: '#FFE500',
    badge: '最受欢迎',
    iconPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>',
    features: [
      { text: '无限 小说项目', ok: true },
      { text: '200次章节生成 / 月', ok: true },
      { text: '多风格灵感缪斯', ok: true },
      { text: '跨界素材嫁接', ok: true },
      { text: '稳定连载生成模式', ok: true },
      { text: '章节体检与返工建议', ok: true },
      { text: '关键章节精修', ok: false },
    ],
  },
  {
    id: 'pro',
    dbId: 3,
    name: '旗舰版',
    price: 69,
    desc: '精品章节与重度创作',
    color: '#C084FC',
    badge: '全功能解锁',
    iconPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>',
    features: [
      { text: '无限 小说项目', ok: true },
      { text: '无限章节生成', ok: true },
      { text: '多方向开局筛选', ok: true },
      { text: '关键章节精修', ok: true },
      { text: '读者模拟与自我批判', ok: true },
      { text: '最高优先队列', ok: true },
      { text: '自定义 LLM 接入（自带 Key）', ok: true },
    ],
  },
]

const comparisonRows: { label: string; vals: (string | boolean)[] }[] = [
  { label: '小说项目数量', vals: ['1 个', '无限', '无限'] },
  { label: '章节生成额度', vals: ['20次/月', '200次/月', '无限次'] },
  { label: '灵感模式增强', vals: ['基础对话', '缪斯 + 素材', '多方向筛选'] },
  { label: '生成质量链路', vals: ['快速生成', '稳定连载', '关键章节精修'] },
  { label: '章节体检', vals: [false, true, true] },
  { label: '长篇一致性工具', vals: [false, true, true] },
  { label: '自定义 LLM 接入', vals: [false, false, true] },
]

const displayPrice = (plan: typeof plans[0]) => {
  if (plan.price === 0) return '¥0'
  return annual.value ? `¥${Math.round(plan.price * 0.8)}` : `¥${plan.price}`
}

const getPlanCardStyle = (plan: typeof plans[0]) => {
  if (plan.id === 'creator') return 'background:linear-gradient(160deg,#1C1A00 0%,#141414 60%);border:1px solid #FFE500;box-shadow:0 0 30px rgba(255,229,0,0.1);'
  if (plan.id === 'pro') return 'background:linear-gradient(160deg,#1A0E2E 0%,#141414 60%);border:1px solid #3D2A5E;'
  return 'background:#141414;border:1px solid #2A2A2A;'
}

// 本地套餐 id → 后端订阅档位（订阅由配额推导，仅有 plan_tier，无具体 plan_id）
const planTier = (plan: typeof plans[0]): string =>
  plan.id === 'pro' ? 'flagship' : plan.id === 'creator' ? 'creator' : 'free'
const isCurrentPremiumPlan = (plan: typeof plans[0]): boolean =>
  currentPlan.value === 'premium' && subscription.value?.plan_tier === planTier(plan)

const getCtaLabel = (plan: typeof plans[0]) => {
  if (plan.id === 'free' && currentPlan.value === 'free' && !isTrialing.value) return '当前套餐'
  if (plan.id === 'free') return '降级'
  if (isCurrentPremiumPlan(plan)) return '当前套餐'
  return '立即订阅'
}

const getCtaStyle = (plan: typeof plans[0]) => {
  const isCurrent = (plan.id === 'free' && currentPlan.value === 'free' && !isTrialing.value) ||
    (isCurrentPremiumPlan(plan))
  if (isCurrent) return 'background:transparent;border:1px solid #2A2A2A;color:#888888;cursor:default;'
  if (plan.id === 'creator') return 'background:#FFE500;color:#000;'
  if (plan.id === 'pro') return 'background:linear-gradient(135deg,#7C3AED,#4F46E5);color:#fff;box-shadow:0 4px 16px rgba(124,58,237,0.3);'
  return 'background:transparent;border:1px solid #2A2A2A;color:#888888;'
}

const closeDialog = () => {
  showUpgradeDialog.value = false
  checkoutLoading.value = false
  checkoutError.value = ''
  checkoutUrl.value = ''
}

const handleUpgrade = async (plan: typeof plans[0]) => {
  if (plan.id === 'free') return
  if (isCurrentPremiumPlan(plan)) return

  showUpgradeDialog.value = true
  checkoutLoading.value = true
  checkoutError.value = ''
  checkoutUrl.value = ''

  try {
    // 后端支持渠道: stripe / alipay / wechat。此处默认走 Stripe（用户指定）。
    // 如需让用户选择渠道，可在升级弹窗加渠道选择器并把 selectedChannel 传入。
    const result = await paymentApi.createOrder(plan.dbId, selectedChannel.value)
    if (result.pay_url) {
      checkoutUrl.value = result.pay_url
      window.open(result.pay_url, '_blank')
    }
  } catch (err: any) {
    checkoutError.value = err?.message || '创建订单失败，请稍后重试'
  } finally {
    checkoutLoading.value = false
  }
}

// 取消订阅：后端无主动取消端点，会员到期自动降级；故移除取消入口(见模板说明)。

onMounted(async () => {
  try {
    subscription.value = await paymentApi.getSubscription()
  } catch {
    // not critical — user may not be authenticated
  }
})
</script>
