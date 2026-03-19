<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="settings-page min-h-screen bg-bg-base">
    <div class="max-w-6xl mx-auto px-6 py-10">
      <!-- Page Header -->
      <div class="settings-header mb-10">
        <div class="flex items-center gap-3 mb-2">
          <div class="header-accent"></div>
          <h1 class="font-display text-[var(--ar-text-h1)] font-bold text-text-primary tracking-tight">
            账号设置
          </h1>
        </div>
        <p class="text-text-muted text-sm ml-[19px]">管理您的系统偏好、大模型配置与账号信息</p>
      </div>

      <div class="flex flex-col md:flex-row gap-8">
        <!-- Sidebar -->
        <div class="w-full md:w-60 shrink-0">
          <div class="settings-sidebar">
            <!-- User Info -->
            <div class="flex items-center gap-3 pb-5 mb-5 sidebar-divider">
              <div class="settings-avatar">
                <span class="settings-avatar-letter">
                  {{ authStore.user?.username?.charAt(0)?.toUpperCase() || '?' }}
                </span>
                <div class="settings-avatar-glow"></div>
              </div>
              <div class="min-w-0">
                <div class="text-text-primary font-medium text-sm truncate">{{ authStore.user?.username || '用户' }}</div>
                <div class="text-text-muted text-xs">{{ authStore.user?.email || '' }}</div>
              </div>
            </div>

            <nav class="space-y-1">
              <button
                @click="activeTab = 'llm'"
                class="settings-nav-item"
                :class="{ active: activeTab === 'llm' }"
              >
                <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><circle cx="12" cy="12" r="3" /></svg>
                <span>LLM配置</span>
                <svg v-if="activeTab === 'llm'" class="w-3.5 h-3.5 ml-auto text-primary opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
              </button>
              <button
                @click="activeTab = 'writing'"
                class="settings-nav-item"
                :class="{ active: activeTab === 'writing' }"
              >
                <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" /></svg>
                <span>写作偏好</span>
              </button>
              <button
                @click="activeTab = 'account'"
                class="settings-nav-item"
                :class="{ active: activeTab === 'account' }"
              >
                <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>
                <span>账号信息</span>
              </button>
            </nav>

            <div class="mt-5 pt-5 sidebar-divider-top">
              <button
                @click="handleLogout"
                class="settings-nav-item logout"
              >
                <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg>
                <span>退出登录</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1 min-w-0">
          <LLMSettings v-if="activeTab === 'llm'" />
          <WritingPreferences v-else-if="activeTab === 'writing'" />
          <div v-else-if="activeTab === 'account'" class="settings-card">
            <div class="settings-card-header">
              <h2 class="font-display text-[var(--ar-text-h2)] font-bold text-text-primary">账号信息</h2>
              <p class="text-text-muted text-xs mt-1 tracking-wide uppercase font-medium">Account Details</p>
            </div>
            <div class="settings-card-body">
              <div class="account-field">
                <span class="account-field-label">用户名</span>
                <p class="account-field-value">{{ authStore.user?.username || '-' }}</p>
              </div>
              <div class="account-field">
                <span class="account-field-label">邮箱</span>
                <p class="account-field-value">{{ authStore.user?.email || '-' }}</p>
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

<style scoped>
/* ---- Page ---- */
.settings-page {
  font-family: var(--ar-font-ui);
}

/* ---- Header ---- */
.settings-header {
  position: relative;
}

.header-accent {
  width: 4px;
  height: 28px;
  background: linear-gradient(180deg, var(--ar-primary), transparent);
  border-radius: 0 var(--ar-radius-xs) var(--ar-radius-xs) 0;
  flex-shrink: 0;
}

/* ---- Sidebar ---- */
.settings-sidebar {
  background-color: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  padding: var(--ar-spacing-5);
  box-shadow: var(--ar-elevation-glow);
  border: 1px solid var(--ar-border);
  position: sticky;
  top: var(--ar-spacing-8);
}

.sidebar-divider {
  border-bottom: 1px solid var(--ar-border);
}

.sidebar-divider-top {
  border-top: 1px solid var(--ar-border);
}

/* ---- Avatar ---- */
.settings-avatar {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: var(--ar-radius-sm);
  background: var(--ar-bg-highlight);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.settings-avatar-letter {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-body-lg);
  font-weight: 700;
  color: var(--ar-primary);
  position: relative;
  z-index: 1;
}

.settings-avatar-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, rgba(250, 204, 21, 0.1) 0%, transparent 70%);
  pointer-events: none;
}

/* ---- Navigation Items ---- */
.settings-nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--ar-spacing-3);
  padding: 10px var(--ar-spacing-4);
  border-radius: var(--ar-radius-sm);
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body);
  font-weight: 500;
  color: var(--ar-text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
  position: relative;
  text-align: left;
}

.settings-nav-item:hover {
  color: var(--ar-text-primary);
  background-color: rgba(255, 255, 255, 0.03);
}

.settings-nav-item.active {
  color: var(--ar-primary);
  background-color: var(--ar-primary-muted);
}

.settings-nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  background: var(--ar-primary);
  border-radius: 0 2px 2px 0;
}

/* Logout variant */
.settings-nav-item.logout {
  color: var(--ar-error);
}

.settings-nav-item.logout:hover {
  background-color: var(--color-error-muted);
  color: var(--ar-error);
}

/* ---- Content Card ---- */
.settings-card {
  background-color: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  box-shadow: var(--ar-elevation-glow);
  overflow: hidden;
}

.settings-card-header {
  padding: var(--ar-spacing-8) var(--ar-spacing-8) var(--ar-spacing-4);
  border-bottom: 1px solid var(--ar-border-subtle);
}

.settings-card-body {
  padding: var(--ar-spacing-6) var(--ar-spacing-8) var(--ar-spacing-8);
  display: flex;
  flex-direction: column;
  gap: var(--ar-spacing-5);
}

/* ---- Account Fields ---- */
.account-field {
  display: flex;
  flex-direction: column;
  gap: var(--ar-spacing-1);
}

.account-field-label {
  font-size: var(--ar-text-label);
  font-weight: 500;
  color: var(--ar-text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.account-field-value {
  font-size: var(--ar-text-body-lg);
  font-weight: 500;
  color: var(--ar-text-primary);
  margin: 0;
}
</style>
