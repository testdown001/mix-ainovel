<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen bg-bg-base">
    <div class="max-w-6xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-text-primary mb-1">账号设置</h1>
      <p class="text-text-secondary text-sm mb-8">管理您的系统偏好、大模型配置与账号信息</p>

      <div class="flex flex-col md:flex-row gap-6">
        <!-- Sidebar -->
        <div class="w-full md:w-60 shrink-0">
          <div class="bg-bg-surface border border-border rounded-2xl p-4">
            <!-- User Info -->
            <div class="flex items-center gap-3 pb-4 mb-4 border-b border-border">
              <div class="w-12 h-12 rounded-full bg-bg-highlight flex items-center justify-center text-text-secondary text-lg font-semibold">
                {{ authStore.user?.username?.charAt(0)?.toUpperCase() || '?' }}
              </div>
              <div class="min-w-0">
                <div class="text-text-primary font-medium text-sm truncate">{{ authStore.user?.username || '用户' }}</div>
                <div class="text-text-muted text-xs">{{ authStore.user?.email || '' }}</div>
              </div>
            </div>

            <nav class="space-y-1">
              <button
                @click="activeTab = 'llm'"
                class="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer"
                :class="activeTab === 'llm' ? 'bg-primary-muted text-primary' : 'text-text-secondary hover:bg-[rgba(255,255,255,0.05)] hover:text-text-primary'"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><circle cx="12" cy="12" r="3" /></svg>
                LLM配置
                <svg v-if="activeTab === 'llm'" class="w-4 h-4 ml-auto" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
              </button>
              <button
                @click="activeTab = 'writing'"
                class="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer"
                :class="activeTab === 'writing' ? 'bg-primary-muted text-primary' : 'text-text-secondary hover:bg-[rgba(255,255,255,0.05)] hover:text-text-primary'"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" /></svg>
                写作偏好
              </button>
              <button
                @click="activeTab = 'account'"
                class="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer"
                :class="activeTab === 'account' ? 'bg-primary-muted text-primary' : 'text-text-secondary hover:bg-[rgba(255,255,255,0.05)] hover:text-text-primary'"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>
                账号信息
              </button>
            </nav>

            <div class="mt-4 pt-4 border-t border-border">
              <button
                @click="handleLogout"
                class="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium text-error hover:bg-error-muted transition-all duration-150 cursor-pointer"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg>
                退出登录
              </button>
            </div>
          </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1 min-w-0">
          <LLMSettings v-if="activeTab === 'llm'" />
          <WritingPreferences v-else-if="activeTab === 'writing'" />
          <div v-else-if="activeTab === 'account'" class="bg-bg-surface border border-border rounded-2xl p-8">
            <h2 class="text-xl font-bold text-text-primary mb-6">账号信息</h2>
            <div class="space-y-4">
              <div>
                <span class="text-text-muted text-sm">用户名</span>
                <p class="text-text-primary font-medium mt-1">{{ authStore.user?.username || '-' }}</p>
              </div>
              <div>
                <span class="text-text-muted text-sm">邮箱</span>
                <p class="text-text-primary font-medium mt-1">{{ authStore.user?.email || '-' }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import LLMSettings from '@/components/LLMSettings.vue';
import WritingPreferences from '@/components/WritingPreferences.vue';

const activeTab = ref<'llm' | 'writing' | 'account'>('llm');
const authStore = useAuthStore();
const router = useRouter();

const handleLogout = () => {
  authStore.logout();
  router.push('/login');
};
</script>
