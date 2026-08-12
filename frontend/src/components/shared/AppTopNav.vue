<!-- AIMETA P=全局顶部导航|R=工作区/设置等页面的统一导航(logo+链接+用户块)|NR=不含通知/下拉菜单|E=component:AppTopNav|X=ui|A=导航|D=vue,auth-store|S=dom -->
<template>
  <header class="sticky top-0 z-40 border-b"
    style="background:rgba(10,10,10,0.85); backdrop-filter:blur(12px); border-color:#2A2A2A;">
    <div class="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
      <!-- Logo -->
      <router-link to="/home" class="flex items-center gap-2.5">
        <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background:#FFE500;">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </div>
        <span class="text-lg font-bold tracking-tight text-white"
          style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
      </router-link>

      <!-- Nav links -->
      <nav class="hidden md:flex items-center gap-7">
        <router-link v-for="link in links" :key="link.to" :to="link.to"
          class="text-sm font-medium transition-colors app-nav-link"
          :class="{ 'app-nav-active': isActive(link.to) }">
          {{ link.label }}
        </router-link>
      </nav>

      <!-- User area -->
      <div class="flex items-center gap-2">
        <router-link v-if="authStore.user?.is_admin" to="/admin"
          class="text-xs px-2.5 py-1.5 rounded-lg border transition-colors app-admin-link"
          style="border-color:#2A2A2A;">
          管理后台
        </router-link>
        <router-link to="/settings" class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg"
          style="border:1px solid #2A2A2A; background:#141414;" title="账户与设置">
          <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
            style="background:#FFE500; color:#000;">
            {{ userInitial }}
          </div>
          <span class="text-sm text-white hidden sm:block">{{ authStore.user?.username || '创作者' }}</span>
        </router-link>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()

const links = [
  { to: '/inspiration', label: '灵感模式' },
  { to: '/workspace', label: '我的小说' },
  { to: '/settings', label: '设置' },
]

const isActive = (to: string) => route.path.startsWith(to)
const userInitial = computed(() => (authStore.user?.username || 'U').charAt(0).toUpperCase())
</script>

<style scoped>
.app-nav-link {
  color: #888888;
}
.app-nav-link:hover {
  color: #ffffff;
}
.app-nav-active {
  color: #ffe500;
}
.app-nav-active:hover {
  color: #ffe500;
}
.app-admin-link {
  color: #888888;
}
.app-admin-link:hover {
  color: #ffe500;
  border-color: #ffe50040 !important;
}
</style>
