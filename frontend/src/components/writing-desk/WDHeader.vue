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
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { NovelProject } from '@/api/novel'

const router = useRouter()
const authStore = useAuthStore()

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

defineProps<Props>()

defineEmits(['goBack', 'viewProjectDetail', 'toggleSidebar'])
</script>
