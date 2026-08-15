<!-- AIMETA P=写作台头部_顶部导航栏|R=导航_操作按钮|NR=不含内容区域|E=component:WDHeader|X=ui|A=头部组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <header class="flex h-14 items-center justify-between border-b shrink-0 z-30 px-4"
    style="background-color: #141414; border-color: #2A2A2A;">
    <!-- Left: back button + novel title -->
    <div class="flex items-center gap-3 min-w-0">
      <button
        @click="$emit('goBack')"
        class="flex items-center justify-center w-8 h-8 rounded-md transition-colors flex-shrink-0"
        style="color: #888888;"
        @mouseenter="($event.target as HTMLElement).style.color='#fff';($event.target as HTMLElement).style.backgroundColor='#2A2A2A'"
        @mouseleave="($event.target as HTMLElement).style.color='#888888';($event.target as HTMLElement).style.backgroundColor='transparent'"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
      </button>

      <div class="flex items-center gap-2 min-w-0">
        <h1 class="text-base font-semibold truncate text-white">{{ project?.title || '加载中...' }}</h1>
        <span v-if="project?.blueprint?.genre"
          class="hidden sm:inline text-xs px-2 py-0.5 rounded-full border flex-shrink-0"
          style="background-color: #1C1C1C; color: #888888; border-color: #2A2A2A;">
          {{ project.blueprint.genre }}
        </span>
        <span class="hidden md:inline text-xs flex-shrink-0" style="color: #888888;">{{ progress }}% 完成</span>
      </div>
    </div>

    <!-- Right: actions -->
    <div class="flex items-center gap-2 flex-shrink-0">
      <!-- Progress bar (desktop) -->
      <div class="hidden lg:flex items-center gap-2 w-40">
        <span class="text-xs whitespace-nowrap" style="color: #888888;">{{ completedChapters }}/{{ totalChapters }}章</span>
        <div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background-color: #1C1C1C;">
          <div class="h-full rounded-full transition-all" style="background-color: #FFE500;"
            :style="{ width: progress + '%' }"></div>
        </div>
      </div>

      <div class="h-4 w-px hidden sm:block" style="background-color: #2A2A2A;"></div>

      <div class="relative hidden sm:block">
        <button
          @click="exportOpen = !exportOpen"
          class="flex items-center gap-1.5 text-sm px-3 h-8 rounded-md border transition-colors"
          style="border-color: #2A2A2A; background-color: transparent; color: #888888;"
        >
          导出全书
        </button>
        <div
          v-if="exportOpen"
          class="absolute right-0 mt-1 w-40 rounded-md border py-1 z-40"
          style="background:#1C1C1C; border-color:#2A2A2A;"
        >
          <button class="w-full text-left px-3 py-1.5 text-sm text-white hover:bg-[#2A2A2A]" :disabled="exporting" @click="exportBook('txt')">导出 TXT</button>
          <button class="w-full text-left px-3 py-1.5 text-sm text-white hover:bg-[#2A2A2A]" :disabled="exporting" @click="exportBook('docx')">导出 DOCX</button>
        </div>
      </div>

      <button
        @click="precheckOpen = true"
        class="hidden md:flex items-center gap-1.5 text-sm px-3 h-8 rounded-md border transition-colors"
        style="border-color: #2A2A2A; background-color: transparent; color: #888888;"
      >
        投稿预检
      </button>

      <button
        @click="$emit('viewProjectDetail')"
        class="hidden sm:flex items-center gap-1.5 text-sm px-3 h-8 rounded-md border transition-colors"
        style="border-color: #2A2A2A; background-color: transparent; color: #888888;"
        @mouseenter="e => { (e.currentTarget as HTMLElement).style.color='#fff'; (e.currentTarget as HTMLElement).style.backgroundColor='#1C1C1C' }"
        @mouseleave="e => { (e.currentTarget as HTMLElement).style.color='#888888'; (e.currentTarget as HTMLElement).style.backgroundColor='transparent' }"
      >
        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path>
          <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path>
        </svg>
        查看详情
      </button>

      <button
        @click="handleLogout"
        class="flex items-center gap-1.5 text-sm px-3 h-8 rounded-md border transition-colors"
        style="border-color: #2A2A2A; background-color: transparent; color: #888888;"
        @mouseenter="e => { (e.currentTarget as HTMLElement).style.color='#fff'; (e.currentTarget as HTMLElement).style.backgroundColor='#1C1C1C' }"
        @mouseleave="e => { (e.currentTarget as HTMLElement).style.color='#888888'; (e.currentTarget as HTMLElement).style.backgroundColor='transparent' }"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
        <span class="hidden md:inline">退出</span>
      </button>

      <!-- Mobile hamburger -->
      <button
        @click="$emit('toggleSidebar')"
        class="flex items-center justify-center w-8 h-8 rounded-md lg:hidden transition-colors"
        style="color: #888888;"
        @mouseenter="e => { (e.currentTarget as HTMLElement).style.color='#fff'; (e.currentTarget as HTMLElement).style.backgroundColor='#2A2A2A' }"
        @mouseleave="e => { (e.currentTarget as HTMLElement).style.color='#888888'; (e.currentTarget as HTMLElement).style.backgroundColor='transparent' }"
      >
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"></path>
        </svg>
      </button>
    </div>
  </header>

  <Teleport to="body">
    <div v-if="precheckOpen" class="fixed inset-0 z-50 flex items-center justify-center" style="background:rgba(0,0,0,0.45)" @click.self="precheckOpen = false">
      <div class="w-[28rem] max-w-[92vw] rounded-xl p-5" style="background:#141414;border:1px solid #2A2A2A;">
        <h3 class="text-white font-semibold mb-1">投稿预检</h3>
        <p class="text-xs mb-4" style="color:#888;">对照平台词表扫描已完稿正文。命中只提示，不会阻止导出或继续写作。</p>
        <select v-model="precheckPlatform" class="w-full mb-3 px-3 py-2 rounded-md text-sm" style="background:#1C1C1C;color:#fff;border:1px solid #2A2A2A;">
          <option value="qidian">起点</option>
          <option value="fanqie">番茄</option>
          <option value="jjwxc">晋江</option>
        </select>
        <div class="flex gap-2 mb-3">
          <button class="px-3 py-1.5 rounded-md text-sm font-semibold" style="background:#FFE500;color:#000;" :disabled="prechecking" @click="runPrecheck">
            {{ prechecking ? '扫描中…' : '开始预检' }}
          </button>
          <button class="px-3 py-1.5 rounded-md text-sm" style="color:#888;" @click="precheckOpen = false">关闭</button>
        </div>
        <p v-if="precheckResult" class="text-sm mb-2" style="color:#ccc;">{{ precheckResult.message }}</p>
        <div v-if="precheckResult?.hits?.length" class="max-h-48 overflow-y-auto space-y-2">
          <div v-for="(hit, i) in precheckResult.hits" :key="i" class="text-xs p-2 rounded" style="background:#1C1C1C;color:#ddd;">
            <span style="color:#C9A227;">{{ hit.term }}</span>
            <p class="mt-1" style="color:#888;">…{{ hit.snippet }}…</p>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { NovelAPI, type CompliancePrecheckResult, type NovelProject } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'

const router = useRouter()
const authStore = useAuthStore()
const exportOpen = ref(false)
const exporting = ref(false)
const precheckOpen = ref(false)
const prechecking = ref(false)
const precheckPlatform = ref<'qidian' | 'fanqie' | 'jjwxc'>('qidian')
const precheckResult = ref<CompliancePrecheckResult | null>(null)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

interface Props {
  project: NovelProject | null
  progress: number
  completedChapters: number
  totalChapters: number
}

const props = defineProps<Props>()

defineEmits(['goBack', 'viewProjectDetail', 'toggleSidebar'])

async function exportBook(format: 'txt' | 'docx') {
  if (!props.project?.id) return
  exporting.value = true
  exportOpen.value = false
  try {
    await NovelAPI.exportManuscript(props.project.id, format)
    globalAlert.showSuccess('已开始下载已完稿章节。', '导出全书')
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '导出失败', '导出全书')
  } finally {
    exporting.value = false
  }
}

async function runPrecheck() {
  if (!props.project?.id) return
  prechecking.value = true
  try {
    precheckResult.value = await NovelAPI.compliancePrecheck(props.project.id, precheckPlatform.value)
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '预检失败', '投稿预检')
  } finally {
    prechecking.value = false
  }
}
</script>
