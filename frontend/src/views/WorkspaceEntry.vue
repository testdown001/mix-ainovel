<!-- AIMETA P=工作区入口_应用主入口|R=入口导航|NR=不含具体功能|E=route:/#component:WorkspaceEntry|X=ui|A=入口页|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen" style="background-color:#0A0A0A; color:#FFFFFF; font-family:'Inter',sans-serif;">

    <!-- Update Log Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center"
      style="background:rgba(0,0,0,0.75);" @click.self="closeModal">
      <div class="w-full max-w-2xl mx-4 rounded-2xl border flex flex-col"
        style="background:#141414; border-color:#2A2A2A; max-height:80vh;">
        <div class="flex items-center justify-between px-6 py-4 border-b" style="border-color:#2A2A2A;">
          <h2 class="text-lg font-bold text-white">系统更新日志</h2>
          <button @click="closeModal" class="text-sm" style="color:#888;">关闭</button>
        </div>
        <div v-if="communityLog" class="px-6 pt-5">
          <div class="p-4 rounded-xl border text-sm" style="background:#1A1600; border-color:#FFE500; color:#FFE500;"
            v-html="renderMarkdown(communityLog.content)"></div>
        </div>
        <div class="px-6 py-5 overflow-y-auto flex-1 space-y-4">
          <div v-for="log in filteredUpdateLogs" :key="log.id"
            class="p-4 rounded-xl border" style="background:#1C1C1C; border-color:#2A2A2A;">
            <div class="text-xs mb-2" style="color:#888888;">{{ new Date(log.created_at).toLocaleDateString() }}</div>
            <div class="text-sm" style="color:#DDDDDD;" v-html="renderMarkdown(log.content)"></div>
          </div>
        </div>
        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t" style="border-color:#2A2A2A;">
          <button @click="hideModalToday" class="text-sm px-4 py-2 rounded-lg transition-colors"
            style="color:#888; background:transparent; border:1px solid #2A2A2A;">
            今日不再显示
          </button>
          <button @click="closeModal" class="text-sm px-5 py-2 rounded-lg font-semibold"
            style="background:#FFE500; color:#000;">
            知道了
          </button>
        </div>
      </div>
    </div>

    <!-- Navigation -->
    <header class="sticky top-0 z-40 border-b" style="background:rgba(10,10,10,0.85); backdrop-filter:blur(12px); border-color:#2A2A2A;">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <!-- Logo -->
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#FFE500;">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </div>
          <span class="text-xl font-bold tracking-tight" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
        </div>

        <!-- Nav links -->
        <nav class="hidden md:flex items-center gap-7">
          <router-link to="/inspiration" class="text-sm font-medium transition-colors"
            style="color:#FFFFFF;"
            active-class="text-yellow-400">灵感模式</router-link>
          <router-link to="/workspace" class="text-sm font-medium transition-colors"
            style="color:#888888;"
            active-class="" @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
            @mouseleave="($event.target as HTMLElement).style.color='#888888'">我的小说</router-link>
          <router-link to="/settings" class="text-sm font-medium transition-colors"
            style="color:#888888;"
            @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
            @mouseleave="($event.target as HTMLElement).style.color='#888888'">设置</router-link>
        </nav>

        <!-- User menu -->
        <div class="flex items-center gap-3">
          <button @click="showModal = updateLogs.length > 0"
            class="relative p-2 rounded-lg transition-colors"
            style="color:#888888;" title="更新日志"
            @mouseenter="($event.target as HTMLElement).style.color='#fff'"
            @mouseleave="($event.target as HTMLElement).style.color='#888888'">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
            </svg>
          </button>

          <div class="relative" ref="dropdownContainer">
            <button @click="userMenuOpen = !userMenuOpen"
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors"
              style="border:1px solid #2A2A2A; background:#141414;">
              <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                style="background:#FFE500; color:#000;">
                {{ userInitials }}
              </div>
              <span class="text-sm text-white hidden sm:block">{{ authStore.user?.username || '创作者' }}</span>
              <svg class="w-3.5 h-3.5 transition-transform" :style="userMenuOpen ? 'transform:rotate(180deg);color:#888' : 'color:#888'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            <div v-if="userMenuOpen" class="absolute right-0 mt-2 w-48 rounded-xl border py-1 z-50"
              style="background:#141414; border-color:#2A2A2A; box-shadow:0 8px 32px rgba(0,0,0,0.5);">
              <router-link to="/settings" @click="userMenuOpen=false"
                class="flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors"
                style="color:#CCCCCC;"
                @mouseenter="($event.target as HTMLElement).style.backgroundColor='#1C1C1C'"
                @mouseleave="($event.target as HTMLElement).style.backgroundColor='transparent'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#888;">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                </svg>
                账户设置
              </router-link>
              <div class="border-t my-1" style="border-color:#2A2A2A;"></div>
              <button @click="handleLogout"
                class="flex items-center gap-2.5 px-4 py-2.5 text-sm w-full text-left transition-colors"
                style="color:#FF4757;"
                @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor='#1C1C1C'"
                @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor='transparent'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                </svg>
                退出登录
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-10">

      <!-- Hero Greeting -->
      <div class="mb-10">
        <h1 class="text-4xl font-bold tracking-tight mb-3" style="font-family:'Space Grotesk',sans-serif;">
          {{ greeting }}，<span style="background:linear-gradient(90deg,#FFE500,#FFB000); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">{{ authStore.user?.username || '创作者' }}</span> 👋
        </h1>
        <p class="text-lg mb-8" style="color:#888888;">准备好继续你的创作之旅了吗？</p>

        <!-- Stats -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl">
          <div class="rounded-xl border p-4 flex flex-col" style="background:#141414; border-color:#2A2A2A;">
            <span class="text-sm font-medium mb-1" style="color:#888888;">已建小说</span>
            <span class="text-3xl font-bold" style="font-family:'Space Grotesk',sans-serif;">{{ novels.length }}</span>
          </div>
          <div class="rounded-xl border p-4 flex flex-col" style="background:#141414; border-color:#2A2A2A;">
            <span class="text-sm font-medium mb-1" style="color:#888888;">已写章节</span>
            <span class="text-3xl font-bold" style="font-family:'Space Grotesk',sans-serif;">{{ totalChapters }}</span>
          </div>
          <div class="rounded-xl border p-4 flex flex-col" style="background:#141414; border-color:#2A2A2A;">
            <span class="text-sm font-medium mb-1" style="color:#888888;">AI生成字数</span>
            <span class="text-3xl font-bold" style="font-family:'Space Grotesk',sans-serif; color:#FFE500;">
              {{ totalWordsDisplay }}<span class="text-base ml-1" style="color:#888888; font-family:'Inter',sans-serif;">w</span>
            </span>
          </div>
          <div class="rounded-xl border p-4 flex flex-col" style="background:#141414; border-color:#2A2A2A;">
            <span class="text-sm font-medium mb-1" style="color:#888888;">更新日志</span>
            <span class="text-3xl font-bold" style="font-family:'Space Grotesk',sans-serif;">{{ updateLogs.length }}</span>
          </div>
        </div>
      </div>

      <!-- Action Cards -->
      <div class="grid md:grid-cols-2 gap-6 mb-10">
        <!-- Inspiration mode -->
        <div @click="goToInspiration"
          class="rounded-2xl border p-8 cursor-pointer transition-all group relative overflow-hidden"
          style="background:linear-gradient(135deg,#1C1C0A 0%,#141414 70%); border-color:rgba(255,229,0,0.3);"
          @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#FFE500'"
          @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='rgba(255,229,0,0.3)'">
          <div class="absolute right-0 top-0 w-48 h-48 rounded-full blur-3xl pointer-events-none"
            style="background:rgba(255,229,0,0.05); transform:translate(30%,-40%);"></div>
          <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-5 transition-transform"
            style="background:rgba(255,229,0,0.1);">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
            </svg>
          </div>
          <h2 class="text-2xl font-bold mb-2 transition-colors text-white"
            style="font-family:'Space Grotesk',sans-serif;">灵感模式</h2>
          <p class="mb-6 text-base" style="color:#888888;">还没有故事？让AI引导你从零开始。设定世界观、构建人物关系、生成完美大纲。</p>
          <span class="inline-flex items-center gap-1.5 text-sm font-semibold" style="color:#FFE500;">
            开始探索
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
            </svg>
          </span>
        </div>

        <!-- Novel library -->
        <div @click="goToWorkspace"
          class="rounded-2xl border p-8 cursor-pointer transition-all group"
          style="background:#141414; border-color:#2A2A2A;"
          @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#FFFFFF'"
          @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='#2A2A2A'">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-5" style="background:#1C1C1C;">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-white mb-2" style="font-family:'Space Grotesk',sans-serif;">我的小说库</h2>
          <p class="mb-6 text-base" style="color:#888888;">查看并管理你所有的小说项目。继续未完成的章节，或者调整已有的设定。</p>
          <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold border transition-colors"
              style="border-color:#2A2A2A; color:#FFFFFF; background:transparent;">
              进入书库
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
              </svg>
            </span>
          </div>
        </div>
      </div>

      <!-- Bottom: Recent Activity + Update Log -->
      <div class="grid md:grid-cols-3 gap-8">

        <!-- Recent novels (2/3 width) -->
        <div class="md:col-span-2">
          <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2" style="font-family:'Space Grotesk',sans-serif;">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#888888;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            最近编辑
          </h3>

          <div v-if="loadingNovels" class="space-y-3">
            <div v-for="i in 3" :key="i" class="h-16 rounded-xl animate-pulse" style="background:#141414;"></div>
          </div>

          <div v-else-if="recentNovels.length === 0"
            class="rounded-xl border p-8 text-center" style="background:#141414; border-color:#2A2A2A;">
            <p style="color:#888888;">还没有小说，去灵感模式开始吧 ✨</p>
            <button @click="goToInspiration"
              class="mt-4 px-4 py-2 rounded-lg text-sm font-semibold"
              style="background:#FFE500; color:#000;">
              开始探索
            </button>
          </div>

          <div v-else class="space-y-3">
            <div v-for="novel in recentNovels" :key="novel.id"
              @click="router.push(`/detail/${novel.id}`)"
              class="flex items-center justify-between p-4 rounded-xl border cursor-pointer group transition-all"
              style="background:#141414; border-color:#2A2A2A;"
              @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#888888'"
              @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='#2A2A2A'">
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center border flex-shrink-0 transition-colors"
                  style="background:#1C1C1C; border-color:#2A2A2A;">
                  <svg class="w-5 h-5 transition-colors" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
                    style="color:#888888;">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                  </svg>
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="font-medium text-white text-sm">{{ novel.title }}</span>
                    <span v-if="novel.is_completed" style="background: rgba(46, 213, 115, 0.15); color: #2ED573; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 999px;">完结</span>
                  </div>
                  <div class="text-xs mt-0.5" style="color:#888888;">
                    {{ novel.completed_chapters }} 章 · {{ novel.genre || '未分类' }}
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-4">
                <div class="hidden sm:flex flex-col items-end">
                  <span class="text-xs mb-1" style="color:#888888;">进度</span>
                  <div class="w-20 h-1.5 rounded-full overflow-hidden" style="background:#1C1C1C;">
                    <div class="h-full rounded-full" style="background:#FFE500;"
                      :style="{ width: `${Math.min(100, (novel.completed_chapters / Math.max(novel.total_chapters || 1, novel.completed_chapters)) * 100)}%` }">
                    </div>
                  </div>
                </div>
                <svg class="w-4 h-4 transition-colors" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#888888;">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- Update log (1/3 width) -->
        <div>
          <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2" style="font-family:'Space Grotesk',sans-serif;">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#888888;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
            </svg>
            系统更新
          </h3>
          <div class="rounded-xl border p-5 relative overflow-hidden" style="background:#141414; border-color:#2A2A2A;">
            <div class="absolute top-0 right-0 w-16 h-16 pointer-events-none"
              style="background:rgba(255,229,0,0.05); border-radius:0 0 0 100%;"></div>

            <div v-if="updateLogs.length === 0" class="text-sm" style="color:#888888;">暂无更新日志</div>

            <div v-for="(log, idx) in updateLogs.slice(0, 2)" :key="log.id"
              :class="idx > 0 ? 'pt-4 mt-4 border-t' : ''"
              :style="idx > 0 ? 'border-color:#2A2A2A;' : ''">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs font-semibold px-2 py-0.5 rounded"
                  :style="idx === 0 ? 'background:rgba(46,213,115,0.15); color:#2ED573;' : 'background:#1C1C1C; color:#888888;'">
                  {{ new Date(log.created_at).toLocaleDateString() }}
                </span>
              </div>
              <div class="text-sm text-white font-medium mb-1 line-clamp-1">{{ extractTitle(log.content) }}</div>
              <div class="text-xs line-clamp-2" style="color:#888888;" v-html="extractSummary(log.content)"></div>
            </div>

            <button v-if="updateLogs.length > 0" @click="showModal = true"
              class="mt-4 text-sm font-medium transition-colors" style="color:#FFE500;">
              查看全部更新日志 →
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getLatestUpdates } from '@/api/updates'
import { NovelAPI } from '@/api/novel'
import type { UpdateLog } from '@/api/updates'
import type { NovelProjectSummary } from '@/api/novel'

marked.setOptions({ gfm: true, breaks: true })
const renderMarkdown = (md: string) => marked.parse(md) as string

const router = useRouter()
const authStore = useAuthStore()

const showModal = ref(false)
const updateLogs = ref<UpdateLog[]>([])
const novels = ref<NovelProjectSummary[]>([])
const loadingNovels = ref(true)
const userMenuOpen = ref(false)
const dropdownContainer = ref<HTMLElement | null>(null)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '深夜好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const userInitials = computed(() => {
  const name = authStore.user?.username || '创'
  return name.slice(0, 1).toUpperCase()
})

const recentNovels = computed(() => novels.value.slice(0, 5))

const totalChapters = computed(() => novels.value.reduce((s, n) => s + (n.completed_chapters || 0), 0))

const totalWordsDisplay = computed(() => {
  const total = novels.value.reduce((s, n) => s + ((n.completed_chapters || 0) * 2000), 0)
  return (total / 10000).toFixed(1)
})

const communityLog = computed(() => updateLogs.value.find(l => /交流群/.test(l.content)))
const filteredUpdateLogs = computed(() =>
  communityLog.value ? updateLogs.value.filter(l => l.id !== communityLog.value!.id) : updateLogs.value
)

const extractTitle = (content: string) => {
  const match = content.match(/^#+\s*(.+)/m)
  return match ? match[1] : content.slice(0, 30) + '...'
}
const extractSummary = (content: string) => {
  const clean = content.replace(/^#+.*$/mg, '').trim().slice(0, 80)
  return clean || '...'
}

onMounted(async () => {
  const hideUntil = localStorage.getItem('hideAnnouncement')
  try {
    updateLogs.value = await getLatestUpdates()
    if (updateLogs.value.length > 0 && hideUntil !== new Date().toDateString()) {
      showModal.value = true
    }
  } catch { /* silent */ }

  try {
    novels.value = await NovelAPI.getAllNovels()
  } catch { /* silent */ } finally {
    loadingNovels.value = false
  }

  document.addEventListener('click', handleOutsideClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutsideClick)
})

const handleOutsideClick = (e: MouseEvent) => {
  if (dropdownContainer.value && !dropdownContainer.value.contains(e.target as Node)) {
    userMenuOpen.value = false
  }
}

const closeModal = () => { showModal.value = false }
const hideModalToday = () => {
  localStorage.setItem('hideAnnouncement', new Date().toDateString())
  closeModal()
}
const handleLogout = () => { authStore.logout(); router.push('/login') }
const goToInspiration = () => router.push('/inspiration')
const goToWorkspace = () => router.push('/workspace')
</script>
