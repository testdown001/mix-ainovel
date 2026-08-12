<!-- AIMETA P=订阅套餐_定价页|R=套餐展示_升级引导|NR=不含支付逻辑|E=route:/pricing#component:PricingView|X=ui|A=定价页|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="min-h-screen" style="background:#0A0A0A; color:#FFFFFF; font-family:'Inter',sans-serif;">

    <!-- Nav -->
    <header class="sticky top-0 z-40 border-b" style="background:rgba(20,20,20,0.9); backdrop-filter:blur(12px); border-color:#2A2A2A;">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#FFE500;">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </div>
          <span class="text-xl font-bold tracking-tight" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
        </div>
        <nav class="hidden md:flex items-center gap-6 text-sm">
          <router-link to="/inspiration" style="color:#888888;"
            @mouseenter="($event.target as HTMLElement).style.color='#fff'"
            @mouseleave="($event.target as HTMLElement).style.color='#888888'">灵感模式</router-link>
          <router-link to="/workspace" style="color:#888888;"
            @mouseenter="($event.target as HTMLElement).style.color='#fff'"
            @mouseleave="($event.target as HTMLElement).style.color='#888888'">我的小说</router-link>
          <router-link to="/settings" style="color:#888888;"
            @mouseenter="($event.target as HTMLElement).style.color='#fff'"
            @mouseleave="($event.target as HTMLElement).style.color='#888888'">设置</router-link>
        </nav>
        <router-link to="/" class="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border transition-colors"
          style="border-color:#2A2A2A; color:#888888;">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          返回
        </router-link>
      </div>
    </header>

    <!-- Trial banner -->
    <div class="border-b" style="background:linear-gradient(90deg,#1A1600,#141414,#1A1600); border-color:#2A2A2A;">
      <div class="max-w-6xl mx-auto px-6 py-3 flex items-center justify-center gap-3">
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span class="text-sm">
          <span class="font-semibold" style="color:#FFE500;">新用户专享：</span>
          <span style="color:#CCCCCC;"> 注册即激活创作者版 </span>
          <span class="font-bold text-white">3天完整试用</span>
          <span style="color:#888888;">，无需绑卡，到期自动降为免费版</span>
        </span>
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
        </svg>
      </div>
    </div>

    <main class="max-w-6xl mx-auto px-6 py-12">

      <!-- Page header -->
      <div class="text-center mb-10">
        <h1 class="text-4xl font-bold mb-3" style="font-family:'Space Grotesk',sans-serif;">选择你的创作套餐</h1>
        <p class="text-lg mb-8" style="color:#888888;">从灵感开局到长篇稳定连载，把 AI 变成可控的创作工作流</p>

        <!-- Annual toggle（仅当后台配置了年付套餐时展示） -->
        <div v-if="hasYearlyPlans" class="inline-flex items-center gap-3 px-4 py-2 rounded-full border" style="background:#141414; border-color:#2A2A2A;">
          <span class="text-sm font-medium" :style="!annual ? 'color:#fff; font-weight:600;' : 'color:#888888;'">按月付费</span>
          <button @click="annual = !annual"
            class="relative w-10 h-5 rounded-full transition-colors flex-shrink-0"
            :style="annual ? 'background:#FFE500;' : 'background:#2A2A2A;'">
            <span class="absolute top-0.5 w-4 h-4 rounded-full transition-all"
              :style="{ left: annual ? 'calc(100% - 18px)' : '2px', background: annual ? '#000' : '#888' }"></span>
          </button>
          <span class="text-sm font-medium" :style="annual ? 'color:#fff; font-weight:600;' : 'color:#888888;'">
            按年付费
            <span class="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full font-bold"
              style="background:rgba(255,229,0,0.15); color:#FFE500;">省20%</span>
          </span>
        </div>
      </div>

      <!-- Plan cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-14">
        <div v-for="plan in displayPlans" :key="plan.id"
          class="relative rounded-2xl flex flex-col transition-all"
          :style="getPlanCardStyle(plan)">

          <!-- Badge -->
          <div v-if="plan.badge" class="absolute -top-3.5 left-0 right-0 flex justify-center">
            <span class="text-xs font-bold px-4 py-1 rounded-full"
              :style="plan.id === 'creator' ? 'background:#FFE500;color:#000;' : 'background:#7C3AED;color:#fff;'">
              {{ plan.badge }}
            </span>
          </div>

          <div class="p-7 flex flex-col flex-1">
            <!-- Plan header -->
            <div class="flex items-center gap-3 mb-5">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                :style="`background:${plan.color}18; border:1px solid ${plan.color}30;`">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
                  :style="`color:${plan.color};`" v-html="plan.iconPath"></svg>
              </div>
              <div>
                <div class="font-bold text-white">{{ plan.name }}</div>
                <div class="text-xs" style="color:#888888;">{{ plan.desc }}</div>
              </div>
            </div>

            <!-- Price -->
            <div class="mb-6 pb-6 border-b" style="border-color:#2A2A2A;">
              <div class="flex items-baseline gap-1">
                <span class="text-4xl font-bold" style="font-family:'Space Grotesk',sans-serif;"
                  :style="plan.price === 0 ? 'color:#888888;' : 'color:#fff;'">
                  {{ displayPrice(plan) }}
                </span>
                <span v-if="plan.price > 0" class="text-sm" style="color:#888888;">
                  {{ annual ? '/ 月（年付）' : '/ 月' }}
                </span>
              </div>
              <div v-if="plan.price === 0" class="text-sm mt-1" style="color:#888888;">永久免费</div>
              <div v-if="plan.price > 0 && annual" class="text-xs mt-1" style="color:#888888;">
                即 <span :style="`color:${plan.color};`">¥{{ Math.round(plan.price * 0.8 * 12) }}</span> / 年
                <span class="ml-1 line-through opacity-50">¥{{ plan.price * 12 }}</span>
              </div>
              <div class="text-sm mt-2 flex items-center gap-1.5" style="color:#aaa;">
                🪙 每月赠
                <span class="font-bold" :style="`color:${plan.color};`">{{ planCredits(plan.id).toLocaleString() }}</span>
                积分
              </div>
            </div>

            <!-- Features -->
            <ul class="space-y-3 flex-1 mb-7">
              <li v-for="f in plan.features" :key="f.text" class="flex items-center gap-2.5 text-sm">
                <div v-if="f.ok" class="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                  :style="`background:${plan.color}20;`">
                  <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"
                    :style="`color:${plan.color};`">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                  </svg>
                </div>
                <div v-else class="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                  style="background:#1C1C1C;">
                  <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"
                    style="color:#444444;">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                </div>
                <span :style="f.ok ? 'color:#DDDDDD;' : 'color:#555555;'">{{ f.text }}</span>
              </li>
              <!-- 灵感缪斯高级能力（与后台档位配置同源，自动同步）-->
              <li v-for="cap in (capsByTier[plan.id] || [])" :key="cap.key"
                  class="flex items-center gap-2.5 text-sm" :title="cap.description">
                <div class="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                  :style="`background:${plan.color}20;`">
                  <span class="text-[10px]" :style="`color:${plan.color};`">⚡</span>
                </div>
                <span style="color:#DDDDDD;">{{ cap.label }}</span>
              </li>
            </ul>

            <!-- CTA -->
            <button @click="handleUpgrade(plan)"
              class="w-full py-3 rounded-xl font-semibold text-sm transition-all"
              :style="getCtaStyle(plan)">
              <span class="flex items-center justify-center gap-2">
                {{ ctaLabel(plan) }}
                <svg v-if="plan.id !== 'free'" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                </svg>
              </span>
            </button>
            <p v-if="plan.id !== 'free'" class="text-center text-[10px] mt-2.5" style="color:#555555;">
              试用期结束自动降为免费版，无需绑卡
            </p>
          </div>
        </div>
      </div>

      <!-- Feature comparison -->
      <div class="mb-14">
        <h2 class="text-xl font-bold text-white mb-5 text-center" style="font-family:'Space Grotesk',sans-serif;">详细功能对比</h2>
        <div class="rounded-xl border overflow-hidden" style="border-color:#2A2A2A;">
          <div class="grid grid-cols-4 border-b text-xs font-semibold" style="background:#141414; border-color:#2A2A2A;">
            <div class="p-4" style="color:#888888;">功能</div>
            <div v-for="plan in displayPlans" :key="plan.id" class="p-4 text-center"
              :style="`color:${plan.color === '#888888' ? '#aaa' : plan.color};`">{{ plan.name }}</div>
          </div>
          <div v-for="(row, i) in comparisonRows" :key="i"
            class="grid grid-cols-4 border-b last:border-0 text-xs"
            :style="i % 2 === 0 ? 'background:#0A0A0A;border-color:#1C1C1C;' : 'background:#141414;border-color:#1C1C1C;'">
            <div class="p-3.5 flex items-center" style="color:#888888;">{{ row.label }}</div>
            <div v-for="(v, j) in row.vals" :key="j" class="p-3.5 flex items-center justify-center">
              <svg v-if="v === true" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#2ED573;">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
              </svg>
              <svg v-else-if="v === false" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#333333;">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
              <span v-else class="font-medium text-white text-center">{{ v }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- FAQ -->
      <div class="max-w-2xl mx-auto mb-14">
        <h2 class="text-xl font-bold text-white mb-6 text-center" style="font-family:'Space Grotesk',sans-serif;">常见问题</h2>
        <div class="space-y-3">
          <div v-for="(faq, i) in faqs" :key="i" class="rounded-xl border overflow-hidden" style="border-color:#2A2A2A;">
            <button @click="openFaq = openFaq === i ? null : i"
              class="w-full flex items-center justify-between gap-4 p-5 text-left transition-colors"
              style="background:#141414;"
              @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor='#1A1A1A'"
              @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor='#141414'">
              <span class="text-sm font-medium text-white">{{ faq.q }}</span>
              <svg class="w-4 h-4 flex-shrink-0 transition-transform" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
                style="color:#888888;" :style="openFaq === i ? 'transform:rotate(180deg);' : ''">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            <div v-if="openFaq === i" class="px-5 pb-5 border-t" style="background:#141414; border-color:#2A2A2A;">
              <p class="text-sm leading-relaxed pt-4" style="color:#888888;">{{ faq.a }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom CTA -->
      <div class="text-center py-12 px-8 rounded-2xl border"
        style="background:linear-gradient(135deg,#1A1600 0%,#0A0A0A 50%,#1A1600 100%); border-color:#2A2A2A;">
        <div class="inline-flex items-center gap-2 text-xs font-semibold tracking-widest uppercase mb-4 px-3 py-1.5 rounded-full border"
          style="color:#FFE500; border-color:rgba(255,229,0,0.2); background:rgba(255,229,0,0.05);">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
          </svg>
          新用户限时优惠
        </div>
        <h3 class="text-2xl font-bold text-white mb-2" style="font-family:'Space Grotesk',sans-serif;">
          现在注册，立享3天创作者版体验
        </h3>
        <p class="mb-8 max-w-md mx-auto text-sm" style="color:#888888;">无需信用卡 · 到期自动降级 · 数据永久保留</p>
        <router-link to="/register"
          class="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-sm transition-colors"
          style="background:#FFE500; color:#000;">
          免费开始创作
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
          </svg>
        </router-link>
      </div>
    </main>

    <!-- Checkout dialog（真实下单：渠道选择 → 创建订单 → 跳转支付） -->
    <div v-if="showCheckout" class="fixed inset-0 z-50 flex items-center justify-center"
      style="background:rgba(0,0,0,0.7);" @click.self="closeCheckout">
      <div class="rounded-2xl border p-8 max-w-sm w-full mx-4 text-center"
        style="background:#141414; border-color:#2A2A2A;">
        <div class="w-12 h-12 rounded-xl mx-auto mb-4 flex items-center justify-center" style="background:rgba(255,229,0,0.1);">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
          </svg>
        </div>
        <h3 class="text-lg font-bold text-white mb-3">
          {{ pendingTier === 'flagship' ? '订阅旗舰版' : '订阅创作者版' }}
        </h3>
        <div class="flex items-center justify-center gap-2 mb-4">
          <button v-for="ch in channelOptions" :key="ch.value" @click="switchChannel(ch.value)"
            class="px-3 py-1 rounded-full text-xs transition-colors"
            :style="selectedChannel === ch.value
              ? 'background:#FFE500;color:#000;font-weight:600;'
              : 'background:#1A1A1A;border:1px solid #2A2A2A;color:#888;'">
            {{ ch.label }}
          </button>
        </div>
        <template v-if="checkoutLoading">
          <div class="flex justify-center my-4">
            <div class="w-6 h-6 border-2 rounded-full animate-spin"
              style="border-color:#FFE500; border-top-color:transparent;"></div>
          </div>
          <p class="text-sm mb-4" style="color:#888888;">正在创建订单...</p>
        </template>
        <template v-else-if="checkoutError">
          <p class="text-sm mb-4" style="color:#FF6B6B;">{{ checkoutError }}</p>
        </template>
        <template v-else-if="checkoutUrl">
          <p class="text-sm mb-4" style="color:#888888;">已在新窗口打开支付页；如未自动打开，请点击下方按钮。</p>
          <a :href="checkoutUrl" target="_blank"
            class="block w-full py-2.5 rounded-lg font-semibold text-sm text-center mb-2.5"
            style="background:#FFE500;color:#000;">
            前往支付
          </a>
        </template>
        <button @click="closeCheckout"
          class="w-full py-2.5 rounded-lg font-semibold text-sm"
          style="background:transparent;border:1px solid #2A2A2A;color:#888888;">
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { plansApi, type PlanCapability } from '@/api/plans'
import { paymentApi, type Plan } from '@/api/payment'
import { resolvePlanForTier } from '@/utils/planResolve'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const annual = ref(false)
const openFaq = ref<number | null>(null)

// 真实收银台（与 SubscriptionPanel 同一套下单链路：套餐解析 → createOrder → 跳转支付）
const showCheckout = ref(false)
const checkoutLoading = ref(false)
const checkoutError = ref('')
const checkoutUrl = ref('')
const pendingTier = ref<'creator' | 'flagship' | null>(null)
const selectedChannel = ref<'stripe' | 'alipay' | 'wechat'>('stripe')
const channelOptions: { value: 'stripe' | 'alipay' | 'wechat'; label: string }[] = [
  { value: 'stripe', label: 'Stripe' },
  { value: 'alipay', label: '支付宝' },
  { value: 'wechat', label: '微信支付' },
]
const backendPlans = ref<Plan[]>([])

// 各档位解锁的高级能力（来自后端 /plans/public，与门控/后台配置同源）
const capsByTier = ref<Record<string, PlanCapability[]>>({})
// 各档位每月积分（来自后端 /plans/public）；拉取前用与后端一致的默认兜底
const creditsByTier = ref<Record<string, number>>({ free: 60, creator: 3000, flagship: 18000 })
// 营销页 plan.id（free/creator/pro）→ 订阅档位
const planIdToTier: Record<string, string> = { free: 'free', creator: 'creator', pro: 'flagship' }
const planCredits = (planId: string): number => {
  const tier = planIdToTier[planId] || 'free'
  return creditsByTier.value[tier] ?? 60
}

onMounted(async () => {
  try {
    const publicPlans = await plansApi.listPublic()
    const map: Record<string, PlanCapability[]> = {}
    const credits: Record<string, number> = {}
    for (const p of publicPlans || []) {
      const tier = (p as any).tier || 'free'
      if (Array.isArray((p as any).capabilities)) map[tier] = (p as any).capabilities
      const c = Number((p as any).monthly_credits) || 0
      if (c > 0) credits[tier] = c
    }
    capsByTier.value = map
    if (Object.keys(credits).length) creditsByTier.value = { ...creditsByTier.value, ...credits }
  } catch {
    // 拉取失败则不展示能力区/用默认积分，不影响定价页其余内容
  }
  try {
    backendPlans.value = await paymentApi.listPlans()
  } catch {
    // 下单时若仍无套餐数据会给出明确报错
  }
})

const plans = [
  {
    id: 'free',
    name: '免费版',
    price: 0,
    desc: '体验完整主线',
    color: '#888888',
    badge: null,
    cta: '当前套餐',
    iconPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>',
    features: [
      { text: '1 个小说项目', ok: true },
      { text: '每月自动发放体验积分', ok: true },
      { text: '灵感到蓝图完整主流程', ok: true },
      { text: '快速生成模式（章鱼1.0）', ok: true },
      { text: '基础角色与大纲管理', ok: true },
      { text: '跨界素材与多缪斯开局', ok: false },
      { text: '稳定连载生成模式', ok: false },
      { text: '关键章节精修', ok: false },
    ],
  },
  {
    id: 'creator',
    name: '创作者版',
    price: 29,
    desc: '稳定连载的最佳选择',
    color: '#FFE500',
    badge: '最受欢迎',
    cta: '免费试用 3 天',
    iconPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>',
    features: [
      { text: '无限小说项目', ok: true },
      { text: '每月充足积分，支撑稳定日更', ok: true },
      { text: '稳定连载生成模式（章鱼2.0）', ok: true },
      { text: '多风格灵感缪斯 + 跨界素材', ok: true },
      { text: '章节体检与返工建议', ok: true },
      { text: '积分加油包随时补充', ok: true },
      { text: '关键章节精修', ok: false },
    ],
  },
  {
    id: 'pro',
    name: '旗舰版',
    price: 69,
    desc: '精品章节与重度创作',
    color: '#C084FC',
    badge: '全功能解锁',
    cta: '免费试用 3 天',
    iconPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>',
    features: [
      { text: '无限小说项目', ok: true },
      { text: '超大月度积分池，重度创作无忧', ok: true },
      { text: '关键章节精修（章鱼3.0 旗舰引擎）', ok: true },
      { text: '概念发散：一次 5 个开局方向', ok: true },
      { text: '卷级复盘与重规划', ok: true },
      { text: '质量回路：两遍制草稿 / 人物意义层', ok: true },
      { text: '全部模型档位与流水线能力', ok: true },
    ],
  },
]

const comparisonRows = computed<{ label: string; vals: (string | boolean)[] }[]>(() => [
  { label: '小说项目数量', vals: ['1 个', '无限', '无限'] },
  {
    label: '每月赠送积分',
    vals: [
      planCredits('free').toLocaleString(),
      planCredits('creator').toLocaleString(),
      planCredits('pro').toLocaleString(),
    ],
  },
  { label: '可用模型档位', vals: ['章鱼1.0', '章鱼1.0 / 2.0', '全部（含章鱼3.0）'] },
  { label: '生成质量链路', vals: ['快速生成', '稳定连载', '关键章节精修'] },
  { label: '灵感模式增强', vals: ['基础对话', '缪斯 + 素材', '多方向筛选'] },
  { label: '章节体检', vals: [false, true, true] },
  { label: '卷级复盘与质量回路', vals: [false, false, true] },
  { label: '积分加油包', vals: [true, true, true] },
])

const faqs = [
  { q: '3天试用需要绑定信用卡吗？', a: '不需要。注册即可激活创作者版3天试用，无需填写任何支付信息。试用到期后自动降为免费版，不会产生任何扣费。' },
  { q: '试用期结束后数据会丢失吗？', a: '不会。你的所有小说项目和章节数据会完整保留。升级后即可继续使用所有内容。' },
  { q: '订阅会自动扣费吗？', a: '不会。订阅按周期一次性支付，到期自动降为免费版，不会自动续费扣款；如需继续使用付费功能，到期前在设置中续费即可（到期前 3 天会有提醒）。' },
  { q: '章节体检有什么用？', a: '章节体检会把生成耗时、RAG 命中、评审分数和正文结构转成可执行的返工建议，帮助你判断这一章是直接定稿、局部修改，还是重新生成。' },
  { q: '积分是怎么消耗的？', a: '生成按所选模型档位计费（例如章鱼2.0 每章 10 积分，可选润色每章 +5），订阅每月自动发放积分。不够用时可购买积分加油包——充值积分永不过期，生成失败自动全额退还。' },
]

const displayPrice = (plan: typeof plans[0]) => {
  if (plan.price === 0) return '¥0'
  return annual.value ? `¥${Math.round(plan.price * 0.8)}` : `¥${plan.price}`
}

const getPlanCardStyle = (plan: typeof plans[0]) => {
  if (plan.id === 'creator') return 'background:linear-gradient(160deg,#1C1A00 0%,#141414 60%);border:1px solid #FFE500;box-shadow:0 0 40px rgba(255,229,0,0.1);'
  if (plan.id === 'pro') return 'background:linear-gradient(160deg,#1A0E2E 0%,#141414 60%);border:1px solid #3D2A5E;box-shadow:0 0 40px rgba(192,132,252,0.08);'
  return 'background:#141414;border:1px solid #2A2A2A;'
}

const getCtaStyle = (plan: typeof plans[0]) => {
  if (plan.id === 'free') return 'background:transparent;border:1px solid #2A2A2A;color:#888888;cursor:default;'
  if (plan.id === 'creator') return 'background:#FFE500;color:#000;'
  return 'background:linear-gradient(135deg,#7C3AED,#4F46E5);color:#fff;box-shadow:0 4px 16px rgba(124,58,237,0.3);'
}

// 用后端真实套餐价格覆盖展示价——营销页硬编码价与后台配置漂移过（页面 ¥29 实际下单 ¥88），
// 属价格欺诈级事故；后端不可达时仍显示模板价，但此时下单同样会被拦截报错
const displayPlans = computed(() =>
  plans.map((p) => {
    if (p.id === 'free') return p
    const matched = resolvePlanForTier(backendPlans.value, planIdToTier[p.id] || '')
    return matched ? { ...p, price: matched.price } : p
  }),
)

// 后台没有年付套餐时隐藏年付开关：否则「省20%」是无法兑现的展示价
const hasYearlyPlans = computed(() =>
  backendPlans.value.some((p) => p.is_active && p.period === 'yearly'),
)

const ctaLabel = (plan: typeof plans[0]): string => {
  if (plan.id === 'free') return authStore.isAuthenticated ? '当前起点' : '免费开始'
  return authStore.isAuthenticated ? '立即订阅' : plan.cta
}

// 后端真实套餐解析：tier → 可下单的 plan.id（共享工具，月付优先，有 Vitest 回归）
const resolvePlanDbId = (tier: string): number | null =>
  resolvePlanForTier(backendPlans.value, tier)?.id ?? null

const closeCheckout = () => {
  showCheckout.value = false
  checkoutLoading.value = false
  checkoutError.value = ''
  checkoutUrl.value = ''
  pendingTier.value = null
}

const createCheckoutOrder = async () => {
  if (!pendingTier.value) return
  checkoutLoading.value = true
  checkoutError.value = ''
  checkoutUrl.value = ''
  try {
    if (!backendPlans.value.length) {
      try {
        backendPlans.value = await paymentApi.listPlans()
      } catch {
        // 下面按 dbId 缺失统一报错
      }
    }
    const dbId = resolvePlanDbId(pendingTier.value)
    if (dbId == null) throw new Error('套餐信息加载失败，请刷新页面后重试')
    const result = await paymentApi.createOrder(dbId, selectedChannel.value)
    if (result.pay_url) {
      checkoutUrl.value = result.pay_url
      window.open(result.pay_url, '_blank')
    } else {
      throw new Error('未获取到支付链接，请换一个支付方式重试')
    }
  } catch (err: any) {
    checkoutError.value = err?.message || '创建订单失败，请稍后重试'
  } finally {
    checkoutLoading.value = false
  }
}

const switchChannel = async (ch: 'stripe' | 'alipay' | 'wechat') => {
  if (selectedChannel.value === ch) return
  selectedChannel.value = ch
  if (showCheckout.value && !checkoutLoading.value) await createCheckoutOrder()
}

const handleUpgrade = async (plan: typeof plans[0]) => {
  if (plan.id === 'free') {
    if (!authStore.isAuthenticated) router.push('/register')
    return
  }
  if (!authStore.isAuthenticated) {
    // 未登录：先注册（注册即享 3 天创作者试用），随后可在本页或设置页完成订阅
    router.push('/register')
    return
  }
  pendingTier.value = (planIdToTier[plan.id] as 'creator' | 'flagship') || 'creator'
  showCheckout.value = true
  await createCheckoutOrder()
}
</script>
