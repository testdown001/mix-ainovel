<template>
  <nav class="neon-navbar">
    <div class="neon-navbar-inner">
      <router-link to="/" class="neon-brand">
        <span class="neon-brand-text">Arboris Novel</span>
      </router-link>

      <div class="hidden sm:flex items-center gap-0.5">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="neon-nav-tab"
          :class="{ 'neon-nav-tab--active': isActive(item.to) }"
        >
          {{ item.label }}
        </router-link>
      </div>

      <div class="flex items-center gap-3">
        <router-link
          v-if="authStore.user?.is_admin"
          to="/admin"
          class="neon-nav-tab"
          :class="{ 'neon-nav-tab--active': isActive('/admin') }"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <span class="hidden md:inline">管理</span>
        </router-link>

        <div class="flex items-center gap-2">
          <button class="neon-icon-btn" title="设置">
            <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>

          <div
            class="neon-avatar"
            @click="handleLogout"
            :title="'退出 (' + (authStore.user?.username || '') + ')'"
          >
            {{ userInitial }}
          </div>
        </div>

        <button @click="mobileMenuOpen = !mobileMenuOpen" class="sm:hidden neon-icon-btn">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path v-if="!mobileMenuOpen" fill-rule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd" />
            <path v-else fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>

    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <div v-if="mobileMenuOpen" class="sm:hidden bg-bg-surface px-4 py-2">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="neon-nav-tab w-full justify-start py-3"
          :class="{ 'neon-nav-tab--active': isActive(item.to) }"
          @click="mobileMenuOpen = false"
        >
          {{ item.label }}
        </router-link>
      </div>
    </transition>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const mobileMenuOpen = ref(false)

const navItems = [
  { to: '/', label: '首页' },
  { to: '/inspiration', label: '灵感模式' },
  { to: '/workspace', label: '我的小说' },
  { to: '/settings', label: '设置' },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const userInitial = computed(() => {
  const name = authStore.user?.username || authStore.user?.email || '?'
  return name.charAt(0).toUpperCase()
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.neon-navbar {
  height: 56px;
  flex-shrink: 0;
  background-color: var(--ar-bg-base);
  position: sticky;
  top: 0;
  z-index: 50;
}

.neon-navbar-inner {
  height: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.neon-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.neon-brand-text {
  font-family: var(--ar-font-display);
  font-size: 18px;
  font-weight: 700;
  font-style: italic;
  color: var(--ar-primary);
  letter-spacing: -0.02em;
}

.neon-nav-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-family: var(--ar-font-ui);
  font-size: 14px;
  font-weight: 500;
  color: var(--ar-text-muted);
  text-decoration: none;
  transition: color 0.15s;
  cursor: pointer;
  background: none;
  border: none;
  position: relative;
}

.neon-nav-tab:hover {
  color: var(--ar-text-primary);
}

.neon-nav-tab--active {
  color: var(--ar-primary);
}

.neon-nav-tab--active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 14px;
  right: 14px;
  height: 2px;
  background: var(--ar-primary);
}

.neon-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ar-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.neon-icon-btn:hover {
  color: var(--ar-text-primary);
  background: rgba(255, 255, 255, 0.04);
}

.neon-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--ar-bg-highlight);
  border: 1px solid rgba(77, 70, 50, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 600;
  color: var(--ar-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.neon-avatar:hover {
  border-color: var(--ar-primary);
  color: var(--ar-primary);
}
</style>
