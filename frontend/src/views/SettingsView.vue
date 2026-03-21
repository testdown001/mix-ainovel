<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen" style="background-color: var(--md-background); color: var(--md-on-surface); font-family: var(--md-font-family);">

    <!-- Top bar -->
    <header class="sticky top-0 z-30 border-b flex items-center gap-4 px-6 h-14" style="background-color: #141414; border-color: #2A2A2A;">
      <router-link to="/" class="flex items-center gap-2 text-sm transition-colors" style="color: #888888;"
        @mouseenter="($event.target as HTMLElement).style.color='#fff'"
        @mouseleave="($event.target as HTMLElement).style.color='#888888'">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
        返回
      </router-link>
      <div class="h-4 w-px" style="background:#2A2A2A;"></div>
      <h1 class="text-sm font-semibold text-white">设置</h1>
    </header>

    <div class="flex max-w-5xl mx-auto px-6 py-8 gap-7">

      <!-- Sidebar -->
      <aside class="w-52 flex-shrink-0">
        <nav class="flex flex-col gap-1">
          <button
            v-for="tab in tabs" :key="tab.id"
            @click="activeTab = tab.id"
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left w-full transition-all"
            :style="activeTab === tab.id
              ? 'background-color:#2A2600; color:#FFE500;'
              : 'background-color:transparent; color:#888888;'"
            @mouseenter="e => { if(activeTab !== tab.id) (e.currentTarget as HTMLElement).style.backgroundColor='#1C1C1C'; (e.currentTarget as HTMLElement).style.color='#fff' }"
            @mouseleave="e => { if(activeTab !== tab.id) { (e.currentTarget as HTMLElement).style.backgroundColor='transparent'; (e.currentTarget as HTMLElement).style.color='#888888' } }"
          >
            <span v-html="tab.icon" class="w-4 h-4 flex-shrink-0"></span>
            {{ tab.label }}
          </button>
        </nav>
      </aside>

      <!-- Content -->
      <main class="flex-1 min-w-0">
        <LLMSettings v-if="activeTab === 'llm'" />
        <WritingPreferences v-else-if="activeTab === 'writing'" />
        <SubscriptionPanel v-else-if="activeTab === 'subscription'" />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import LLMSettings from '@/components/LLMSettings.vue'
import WritingPreferences from '@/components/WritingPreferences.vue'
import SubscriptionPanel from '@/components/SubscriptionPanel.vue'

type TabId = 'llm' | 'writing' | 'subscription'

const activeTab = ref<TabId>('llm')

const tabs = [
  {
    id: 'llm' as TabId,
    label: 'LLM 配置',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>',
  },
  {
    id: 'writing' as TabId,
    label: '写作偏好',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>',
  },
  {
    id: 'subscription' as TabId,
    label: '会员套餐',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>',
  },
]
</script>
