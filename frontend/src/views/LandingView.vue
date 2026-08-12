<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

interface Plan {
  id: string | number
  name: string
  description: string
  price: number
  period: string
  daily_chapter_limit: number
  max_novels: number
  features: string[]
  is_recommended: boolean
  is_active: boolean
}

const plans = ref<Plan[]>([])
const plansLoading = ref(true)
const annual = ref(false)
const mobileMenuOpen = ref(false)

const planColors = ['#6B7280', '#FFE500', '#A78BFA']
const planColorsBg = ['#6B728015', '#FFE50012', '#A78BFA15']
const planColorsBorder = ['#6B728030', '#FFE50030', '#A78BFA30']

function getPlanColor(idx: number) { return planColors[idx % planColors.length] }
function getPlanColorBg(idx: number) { return planColorsBg[idx % planColorsBg.length] }
function getPlanColorBorder(idx: number) { return planColorsBorder[idx % planColorsBorder.length] }

function displayPrice(plan: Plan): string {
  if (plan.price === 0) return '免费'
  const base = annual.value ? Math.round(plan.price * 0.8) : plan.price
  return `¥${base}`
}

function periodLabel(plan: Plan): string {
  if (plan.price === 0) return '永久免费'
  if (plan.period === 'yearly' || plan.period === 'annual') return annual.value ? '/ 月（年付）' : '/ 月'
  return annual.value ? '/ 月（年付）' : '/ 月'
}

function getCtaText(plan: Plan): string {
  if (plan.price === 0) return '免费开始创作'
  return '立即开通'
}

function handleCta(plan: Plan) {
  if (auth.isAuthenticated) {
    router.push('/pricing')
  } else {
    router.push('/register')
  }
}

function goStart() {
  if (auth.isAuthenticated) {
    router.push('/home')
  } else {
    router.push('/register')
  }
}

async function fetchPlans() {
  try {
    const res = await fetch('/api/plans/public')
    if (res.ok) {
      plans.value = await res.json()
    }
  } catch {
    plans.value = []
  } finally {
    plansLoading.value = false
  }
}

onMounted(fetchPlans)

const features = [
  {
    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>`,
    title: '自创先进多 Agent 架构',
    subtitle: '为长篇网文定制的协作引擎',
    desc: '规划、生成、审核、记忆与技能模块协同工作，从章节目标到成稿质量全链路把关，让每章创作都达到发布水准。',
    color: '#FFE500',
  },
  {
    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>`,
    title: '灵感引爆系统',
    subtitle: '永远不再面对空白页',
    desc: '多维度灵感生成引擎，结合角色、世界观、情节逻辑，在你最需要的时刻提供精准的创作方向与素材。',
    color: '#A78BFA',
  },
  {
    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>`,
    title: '伏笔智能追踪',
    subtitle: '百万字也不遗漏细节',
    desc: '自动建立伏笔与世界观知识图谱，追踪每一条线索的发展状态，为作者织就无懈可击的故事网络。',
    color: '#34D399',
  },
  {
    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>`,
    title: '章节质量审核',
    subtitle: '出版级标准智能把关',
    desc: '面向长篇连载的章节评审系统，从文笔流畅度、情节连贯性到角色一致性，多维度打分并提出优化建议。',
    color: '#F97316',
  },
  {
    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>`,
    title: '角色与世界观管理',
    subtitle: '构建你的专属宇宙',
    desc: '可视化管理所有角色关系、势力图谱、地图设定与力量体系，让宏大的世界观始终清晰有序。',
    color: '#60A5FA',
  },
  {
    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>`,
    title: '写作数据分析',
    subtitle: '量化你的创作成长',
    desc: '实时追踪字数、章节完成率、AI助力比例等核心指标，帮助你持续优化写作习惯与效率。',
    color: '#FB7185',
  },
]

const steps = [
  { num: '01', title: '创建你的小说项目', desc: '填写书名、类型与核心设定，AI帮你拓展世界观与角色体系', icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>` },
  { num: '02', title: '激活多 Agent 协作', desc: '规划智能体分析章节目标，生成、审核、记忆模块协同完成高质量草稿', icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>` },
  { num: '03', title: '审核与完善章节', desc: '质量审核智能体自动评估，你只需确认并微调，章节即可达到发布水准', icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>` },
  { num: '04', title: '持续积累，完成大作', desc: '每日高效产出，伏笔追踪确保故事无漏，朝百万字长篇迈进', icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>` },
]

const stats = [
  { value: '多引擎', label: '智能调度 · 顶尖大模型' },
  { value: '全流程', label: '灵感 → 蓝图 → 连载' },
  { value: '积分制', label: '按量计费 · 充值不过期' },
  { value: '3天', label: '注册即享创作者版试用' },
]
</script>

<template>
  <div class="min-h-screen" style="background:#0A0A0A; color:#FFFFFF; font-family:'Inter',sans-serif; overflow-x:hidden;">

    <!-- ───── NAVBAR ───── -->
    <header class="sticky top-0 z-50 border-b" style="background:rgba(10,10,10,0.88); backdrop-filter:blur(16px); border-color:#1E1E1E;">
      <div class="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <!-- Logo -->
        <div class="flex items-center gap-2.5 cursor-pointer" @click="router.push('/')">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background:#FFE500;">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </div>
          <span class="text-xl font-bold tracking-tight" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
        </div>

        <!-- Desktop Nav -->
        <nav class="hidden md:flex items-center gap-7 text-sm" style="color:#888888;">
          <a href="#features" style="color:#888888;" class="hover-white transition-colors">功能特性</a>
          <a href="#how" style="color:#888888;" class="hover-white transition-colors">工作原理</a>
          <a href="#pricing" style="color:#888888;" class="hover-white transition-colors">套餐价格</a>
        </nav>

        <!-- CTA Buttons -->
        <div class="hidden md:flex items-center gap-3">
          <router-link v-if="auth.isAuthenticated" to="/home"
            class="text-sm px-4 py-2 rounded-lg font-semibold transition-all"
            style="background:#FFE500; color:#000;">
            进入工作台
          </router-link>
          <template v-else>
            <router-link to="/login" class="text-sm px-4 py-2 rounded-lg border transition-all"
              style="border-color:#2A2A2A; color:#CCCCCC;"
              @mouseenter="($event.target as HTMLElement).style.borderColor='#555'"
              @mouseleave="($event.target as HTMLElement).style.borderColor='#2A2A2A'">
              登录
            </router-link>
            <router-link to="/register" class="text-sm px-4 py-2 rounded-lg font-semibold transition-all"
              style="background:#FFE500; color:#000;">
              免费开始
            </router-link>
          </template>
        </div>

        <!-- Mobile menu button -->
        <button class="md:hidden p-2 rounded-lg" style="color:#888;" @click="mobileMenuOpen = !mobileMenuOpen">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path v-if="!mobileMenuOpen" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
            <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <!-- Mobile menu -->
      <div v-if="mobileMenuOpen" class="md:hidden border-t px-6 py-4 space-y-3" style="background:#0F0F0F; border-color:#1E1E1E;">
        <a href="#features" @click="mobileMenuOpen=false" class="block text-sm py-2" style="color:#CCCCCC;">功能特性</a>
        <a href="#how" @click="mobileMenuOpen=false" class="block text-sm py-2" style="color:#CCCCCC;">工作原理</a>
        <a href="#pricing" @click="mobileMenuOpen=false" class="block text-sm py-2" style="color:#CCCCCC;">套餐价格</a>
        <div class="flex gap-3 pt-2">
          <router-link v-if="auth.isAuthenticated" to="/home" class="flex-1 text-center text-sm py-2 rounded-lg font-semibold" style="background:#FFE500; color:#000;">进入工作台</router-link>
          <template v-else>
            <router-link to="/login" class="flex-1 text-center text-sm py-2 rounded-lg border" style="border-color:#2A2A2A; color:#CCC;">登录</router-link>
            <router-link to="/register" class="flex-1 text-center text-sm py-2 rounded-lg font-semibold" style="background:#FFE500; color:#000;">免费开始</router-link>
          </template>
        </div>
      </div>
    </header>

    <!-- ───── TRIAL BANNER ───── -->
    <div style="background:linear-gradient(90deg,#130F00,#0F0F0F,#130F00); border-bottom:1px solid #1E1E1E;">
      <div class="max-w-7xl mx-auto px-6 py-2.5 flex items-center justify-center gap-3 text-sm">
        <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        <span style="color:#888888;">新用户注册即享</span>
        <span class="font-bold" style="color:#FFE500;">创作者版 3 天完整体验</span>
        <span style="color:#555;">·</span>
        <span style="color:#888888;">无需绑卡，到期自动降为免费版</span>
      </div>
    </div>

    <!-- ───── HERO ───── -->
    <section class="relative overflow-hidden" style="padding:80px 24px 100px;">
      <!-- Background glow -->
      <div class="absolute inset-0 pointer-events-none" style="background:radial-gradient(ellipse 70% 50% at 50% 0%, rgba(255,229,0,0.07) 0%, transparent 70%);"></div>
      <!-- Grid lines -->
      <div class="absolute inset-0 pointer-events-none" style="background-image:linear-gradient(#1A1A1A 1px,transparent 1px),linear-gradient(90deg,#1A1A1A 1px,transparent 1px);background-size:64px 64px;opacity:0.4;"></div>

      <div class="relative max-w-4xl mx-auto text-center">
        <!-- Tag -->
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border mb-8 text-xs font-medium"
          style="background:#141400; border-color:#FFE50030; color:#FFE500;">
          <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" style="background:#FFE500;"></span>
          自创先进多 Agent 架构 · AI 驱动的中国网络小说创作平台
        </div>

        <!-- Headline -->
        <h1 class="font-extrabold mb-6 leading-tight" style="font-family:'Space Grotesk',sans-serif; font-size:clamp(2.5rem,6vw,4.5rem); letter-spacing:-0.02em;">
          让每一位创作者<br>
          <span style="color:#FFE500;">都有百万字长篇</span>的能力
        </h1>

        <!-- Subheadline -->
        <p class="text-lg mb-10 max-w-2xl mx-auto" style="color:#888888; line-height:1.7;">
          Octopus AI Novel 用我们自创的先进多 Agent 架构，帮你突破创作瓶颈——
          从灵感到定稿，全流程 AI 加持，让日更 5000 字成为常态。
        </p>

        <!-- CTAs -->
        <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button @click="goStart"
            class="flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-sm transition-all"
            style="background:#FFE500; color:#000;"
            @mouseenter="($event.currentTarget as HTMLElement).style.background='#FFF000'"
            @mouseleave="($event.currentTarget as HTMLElement).style.background='#FFE500'">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
            {{ auth.isAuthenticated ? '进入工作台' : '免费开始创作' }}
          </button>
          <a href="#how" class="flex items-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-sm border transition-all"
            style="border-color:#2A2A2A; color:#CCCCCC;"
            @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#444'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='#2A2A2A'">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            了解工作原理
          </a>
        </div>

        <!-- Trust signals -->
        <div class="mt-12 flex flex-wrap items-center justify-center gap-6" style="color:#555; font-size:0.8rem;">
          <span class="flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20" style="color:#FFE500;"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
            无需绑定信用卡
          </span>
          <span class="flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20" style="color:#FFE500;"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
            注册即享创作者版 3 天试用
          </span>
          <span class="flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20" style="color:#FFE500;"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
            随时取消，无锁定期
          </span>
        </div>
      </div>
    </section>

    <!-- ───── STATS ───── -->
    <section style="border-top:1px solid #1A1A1A; border-bottom:1px solid #1A1A1A; background:#0D0D0D; padding:48px 24px;">
      <div class="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
        <div v-for="s in stats" :key="s.label">
          <div class="text-3xl font-bold mb-1" style="font-family:'Space Grotesk',sans-serif; color:#FFE500;">{{ s.value }}</div>
          <div class="text-sm" style="color:#666;">{{ s.label }}</div>
        </div>
      </div>
    </section>

    <!-- ───── FEATURES ───── -->
    <section id="features" style="padding:96px 24px;">
      <div class="max-w-7xl mx-auto">
        <div class="text-center mb-16">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-5"
            style="background:#1A1A1A; border:1px solid #2A2A2A; color:#888;">
            核心功能
          </div>
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="font-family:'Space Grotesk',sans-serif;">
            为中国网络小说而生的<br><span style="color:#FFE500;">全套创作工具链</span>
          </h2>
          <p class="text-base max-w-xl mx-auto" style="color:#666;">
            不是简单的 AI 写作工具，而是一套完整的智能创作工作流，覆盖你从构思到完稿的每一个环节。
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div v-for="f in features" :key="f.title"
            class="rounded-2xl border p-6 transition-all group"
            style="background:#0D0D0D; border-color:#1E1E1E;"
            @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#2A2A2A'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='#1E1E1E'">
            <div class="w-11 h-11 rounded-xl flex items-center justify-center mb-5"
              :style="`background:${f.color}12; border:1px solid ${f.color}25;`">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"
                :style="`color:${f.color};`" v-html="f.icon"></svg>
            </div>
            <div class="font-semibold text-white mb-1">{{ f.title }}</div>
            <div class="text-xs mb-3" :style="`color:${f.color}; opacity:0.85;`">{{ f.subtitle }}</div>
            <p class="text-sm leading-relaxed" style="color:#666;">{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ───── HOW IT WORKS ───── -->
    <section id="how" style="padding:96px 24px; background:#060606;">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-16">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-5"
            style="background:#1A1A1A; border:1px solid #2A2A2A; color:#888;">
            工作流程
          </div>
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="font-family:'Space Grotesk',sans-serif;">
            四步开启你的<span style="color:#FFE500;">高效创作之旅</span>
          </h2>
          <p class="text-base max-w-xl mx-auto" style="color:#666;">
            从零开始，到每日稳定产出，只需四个简单步骤。
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div v-for="(step, i) in steps" :key="step.num" class="relative">
            <!-- Connector line -->
            <div v-if="i < steps.length - 1" class="hidden lg:block absolute top-8 left-1/2 w-full h-px" style="background:linear-gradient(90deg,#2A2A2A,transparent); transform:translateX(50%); z-index:0;"></div>
            <div class="relative z-10 rounded-2xl border p-6" style="background:#0D0D0D; border-color:#1E1E1E;">
              <div class="text-5xl font-black mb-4" style="font-family:'Space Grotesk',sans-serif; color:#1A1A1A; line-height:1;">{{ step.num }}</div>
              <div class="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style="background:#FFE50012; border:1px solid #FFE50025;">
                <svg class="w-4.5 h-4.5 w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;" v-html="step.icon"></svg>
              </div>
              <div class="font-semibold text-white mb-2 text-sm">{{ step.title }}</div>
              <p class="text-xs leading-relaxed" style="color:#666;">{{ step.desc }}</p>
            </div>
          </div>
        </div>

        <!-- Central CTA -->
        <div class="mt-14 text-center">
          <button @click="goStart"
            class="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-sm transition-all"
            style="background:#FFE500; color:#000;"
            @mouseenter="($event.currentTarget as HTMLElement).style.background='#FFF000'"
            @mouseleave="($event.currentTarget as HTMLElement).style.background='#FFE500'">
            {{ auth.isAuthenticated ? '返回工作台' : '立即免费体验' }}
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
          </button>
        </div>
      </div>
    </section>

    <!-- ───── PRICING ───── -->
    <section id="pricing" style="padding:96px 24px;">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-12">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-5"
            style="background:#1A1A1A; border:1px solid #2A2A2A; color:#888;">
            套餐价格
          </div>
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="font-family:'Space Grotesk',sans-serif;">
            选择适合你的<span style="color:#FFE500;">创作套餐</span>
          </h2>
          <p class="text-base max-w-xl mx-auto mb-8" style="color:#666;">
            从免费版开始，随时升级；注册即享创作者版 3 天完整试用，积分不够可随时购买加油包。
          </p>

          <!-- Billing toggle -->
          <div class="inline-flex items-center gap-3 px-4 py-2 rounded-full border text-sm"
            style="background:#0D0D0D; border-color:#2A2A2A;">
            <span :style="!annual ? 'color:#fff; font-weight:600;' : 'color:#666;'" class="transition-colors">按月付费</span>
            <button @click="annual = !annual"
              class="relative w-10 h-5 rounded-full transition-colors flex-shrink-0"
              :style="annual ? 'background:#FFE500;' : 'background:#2A2A2A;'">
              <span class="absolute top-0.5 w-4 h-4 rounded-full transition-all"
                :style="{ left: annual ? 'calc(100% - 18px)' : '2px', background: annual ? '#000' : '#555' }"></span>
            </button>
            <span :style="annual ? 'color:#fff; font-weight:600;' : 'color:#666;'" class="transition-colors flex items-center gap-2">
              按年付费
              <span class="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
                style="background:rgba(255,229,0,0.15); color:#FFE500;">省20%</span>
            </span>
          </div>
        </div>

        <!-- Loading skeleton -->
        <div v-if="plansLoading" class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div v-for="i in 3" :key="i" class="rounded-2xl border h-96 animate-pulse" style="background:#0D0D0D; border-color:#1E1E1E;"></div>
        </div>

        <!-- Plan cards -->
        <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div v-for="(plan, idx) in plans" :key="plan.id"
            class="relative rounded-2xl flex flex-col transition-all"
            :style="plan.is_recommended
              ? `background:#111000; border:1.5px solid ${getPlanColor(idx)}50; box-shadow:0 0 40px ${getPlanColor(idx)}08;`
              : `background:#0D0D0D; border:1px solid #1E1E1E;`">

            <!-- Recommended badge -->
            <div v-if="plan.is_recommended" class="absolute -top-3.5 left-0 right-0 flex justify-center">
              <span class="text-xs font-bold px-4 py-1 rounded-full" style="background:#FFE500; color:#000;">
                ⭐ 最受欢迎
              </span>
            </div>

            <div class="p-7 flex flex-col flex-1">
              <!-- Header -->
              <div class="flex items-center gap-3 mb-6">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  :style="`background:${getPlanColorBg(idx)}; border:1px solid ${getPlanColorBorder(idx)};`">
                  <svg class="w-4.5 h-4.5 w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
                    :style="`color:${getPlanColor(idx)};`">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
                  </svg>
                </div>
                <div>
                  <div class="font-bold text-white">{{ plan.name }}</div>
                  <div class="text-xs" style="color:#666;">{{ plan.description }}</div>
                </div>
              </div>

              <!-- Price -->
              <div class="pb-5 mb-5 border-b" style="border-color:#1E1E1E;">
                <div class="flex items-baseline gap-1.5">
                  <span class="text-4xl font-bold" style="font-family:'Space Grotesk',sans-serif;"
                    :style="plan.price === 0 ? 'color:#555;' : 'color:#fff;'">
                    {{ displayPrice(plan) }}
                  </span>
                  <span v-if="plan.price > 0" class="text-xs" style="color:#555;">{{ periodLabel(plan) }}</span>
                </div>
                <div v-if="plan.price === 0" class="text-xs mt-1" style="color:#555;">永久免费，无限期使用</div>
                <div v-if="plan.price > 0 && annual" class="text-xs mt-1" style="color:#555;">
                  即 <span :style="`color:${getPlanColor(idx)};`">¥{{ Math.round(plan.price * 0.8 * 12) }}</span> / 年
                  <span class="ml-1 line-through opacity-40">¥{{ plan.price * 12 }}</span>
                </div>
              </div>

              <!-- Features -->
              <ul class="space-y-2.5 flex-1 mb-7">
                <li v-for="feat in plan.features" :key="feat" class="flex items-center gap-2.5 text-sm">
                  <div class="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                    :style="`background:${getPlanColor(idx)}18;`">
                    <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"
                      :style="`color:${getPlanColor(idx)};`">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                  </div>
                  <span style="color:#BBBBBB;">{{ feat }}</span>
                </li>
              </ul>

              <!-- CTA -->
              <button @click="handleCta(plan)"
                class="w-full py-3 rounded-xl font-semibold text-sm transition-all"
                :style="plan.is_recommended
                  ? 'background:#FFE500; color:#000;'
                  : 'background:#1A1A1A; color:#CCCCCC; border:1px solid #2A2A2A;'"
                @mouseenter="(e) => { if(plan.is_recommended)(e.currentTarget as HTMLElement).style.background='#FFF000'; else (e.currentTarget as HTMLElement).style.borderColor='#444'; }"
                @mouseleave="(e) => { if(plan.is_recommended)(e.currentTarget as HTMLElement).style.background='#FFE500'; else (e.currentTarget as HTMLElement).style.borderColor='#2A2A2A'; }">
                {{ getCtaText(plan) }}
              </button>
              <p v-if="plan.price > 0" class="text-center text-[10px] mt-2" style="color:#444;">
                3天免费体验 · 无需绑卡 · 到期自动降级
              </p>
            </div>
          </div>
        </div>

        <!-- Enterprise note -->
        <div class="mt-10 text-center p-6 rounded-2xl border" style="background:#0D0D0D; border-color:#1E1E1E;">
          <div class="text-sm font-medium text-white mb-1">需要团队协作或企业定制方案？</div>
          <p class="text-xs mb-3" style="color:#555;">我们提供专属的企业版功能，包括多人协作、自定义模型部署和API接入。</p>
          <a href="mailto:hi@octopusainovel.com" class="inline-flex items-center gap-1.5 text-sm font-medium transition-colors"
            style="color:#FFE500;"
            @mouseenter="($event.currentTarget as HTMLElement).style.opacity='0.8'"
            @mouseleave="($event.currentTarget as HTMLElement).style.opacity='1'">
            联系我们
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
          </a>
        </div>
      </div>
    </section>

    <!-- ───── FAQ ───── -->
    <section style="padding:0 24px 96px;">
      <div class="max-w-3xl mx-auto">
        <h2 class="text-2xl font-bold text-center mb-10" style="font-family:'Space Grotesk',sans-serif;">常见问题</h2>
        <div class="space-y-3">
          <details v-for="faq in [
            {q:'AI生成的内容版权归谁？', a:'所有由你输入的内容及AI输出的结果，版权完全归你所有。我们不会使用你的创作内容训练模型或用于其他用途。'},
            {q:'免费版和付费版有什么区别？', a:'免费版每日可生成3章，最多管理2个项目，适合轻度体验。付费版解锁更高每日章节数、更多项目、完整的先进多 Agent 协作系统及高级功能。'},
            {q:'如何取消订阅？', a:'你可以在「设置」→「账户」中随时一键取消，取消后仍可使用至当前账单周期结束，不会立即降级。'},
            {q:'支持哪些支付方式？', a:'目前支持支付宝、微信支付和国际信用卡（通过Stripe）。后续将持续扩展更多支付渠道。'},
            {q:'AI写的内容质量如何把控？', a:'我们的质量审核智能体会自动对每章内容进行多维评分，包括文笔、逻辑和角色一致性，并给出修改建议，最终定稿权始终在你手中。'},
          ]" :key="faq.q"
            class="rounded-xl border overflow-hidden"
            style="background:#0D0D0D; border-color:#1E1E1E;">
            <summary class="flex items-center justify-between px-5 py-4 cursor-pointer list-none text-sm font-medium text-white select-none"
              style="outline:none;">
              {{ faq.q }}
              <svg class="w-4 h-4 flex-shrink-0 transition-transform" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#555;"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
            </summary>
            <div class="px-5 pb-4 text-sm leading-relaxed" style="color:#666; border-top:1px solid #1A1A1A; padding-top:14px;">{{ faq.a }}</div>
          </details>
        </div>
      </div>
    </section>

    <!-- ───── BOTTOM CTA ───── -->
    <section style="padding:80px 24px; background:#060606; border-top:1px solid #1A1A1A;">
      <div class="max-w-3xl mx-auto text-center">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-medium mb-8"
          style="background:#141400; border-color:#FFE50030; color:#FFE500;">
          <span class="w-1.5 h-1.5 rounded-full" style="background:#FFE500;"></span>
          现在开始，3天完整体验
        </div>
        <h2 class="text-3xl md:text-4xl font-bold mb-5" style="font-family:'Space Grotesk',sans-serif;">
          你的第一部百万字<br>长篇，从今天开始
        </h2>
        <p class="text-base mb-10 max-w-md mx-auto" style="color:#666;">
          加入已有 10,000+ 创作者的 Octopus AI Novel，用 AI 的力量释放你的故事。
        </p>
        <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button @click="goStart"
            class="flex items-center gap-2 px-10 py-4 rounded-xl font-bold transition-all"
            style="background:#FFE500; color:#000; font-size:0.95rem;"
            @mouseenter="($event.currentTarget as HTMLElement).style.background='#FFF000'"
            @mouseleave="($event.currentTarget as HTMLElement).style.background='#FFE500'">
            {{ auth.isAuthenticated ? '返回工作台' : '免费注册，立即体验' }}
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
          </button>
          <router-link v-if="!auth.isAuthenticated" to="/login" class="text-sm" style="color:#555;">
            已有账号？<span style="color:#888;">直接登录</span>
          </router-link>
        </div>
      </div>
    </section>

    <!-- ───── FOOTER ───── -->
    <footer style="border-top:1px solid #141414; padding:40px 24px; background:#060606;">
      <div class="max-w-6xl mx-auto">
        <div class="flex flex-col md:flex-row items-start justify-between gap-10 mb-10">
          <!-- Brand -->
          <div class="max-w-xs">
            <div class="flex items-center gap-2.5 mb-3">
              <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background:#FFE500;">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
              </div>
              <span class="font-bold" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
            </div>
            <p class="text-xs leading-relaxed" style="color:#444;">AI驱动的中国网络小说创作平台，用自创先进多 Agent 架构助力每一位创作者。</p>
          </div>
          <!-- Links -->
          <div class="grid grid-cols-2 md:grid-cols-3 gap-8 text-sm">
            <div>
              <div class="font-medium mb-3 text-xs tracking-widest" style="color:#666; text-transform:uppercase;">产品</div>
              <div class="space-y-2">
                <a href="#features" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">功能特性</a>
                <a href="#pricing" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">套餐价格</a>
                <router-link to="/register" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">免费注册</router-link>
              </div>
            </div>
            <div>
              <div class="font-medium mb-3 text-xs tracking-widest" style="color:#666; text-transform:uppercase;">账户</div>
              <div class="space-y-2">
                <router-link to="/login" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">登录</router-link>
                <router-link to="/register" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">注册</router-link>
                <router-link to="/pricing" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">升级套餐</router-link>
              </div>
            </div>
            <div>
              <div class="font-medium mb-3 text-xs tracking-widest" style="color:#666; text-transform:uppercase;">联系</div>
              <div class="space-y-2">
                <a href="mailto:hi@octopusainovel.com" class="block transition-colors" style="color:#444;" @mouseenter="($event.target as HTMLElement).style.color='#888'" @mouseleave="($event.target as HTMLElement).style.color='#444'">邮件联系</a>
              </div>
            </div>
          </div>
        </div>
        <div class="flex flex-col md:flex-row items-center justify-between gap-3 pt-6" style="border-top:1px solid #141414;">
          <p class="text-xs" style="color:#333;">© 2025 Octopus AI Novel. 保留所有权利。</p>
          <p class="text-xs" style="color:#333;">Powered by AI · 自创先进多 Agent 协作架构</p>
        </div>
      </div>
    </footer>

  </div>
</template>

<style scoped>
details > summary::-webkit-details-marker { display: none; }
details[open] > summary svg { transform: rotate(180deg); }
</style>
