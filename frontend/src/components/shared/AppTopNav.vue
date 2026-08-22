<!-- AIMETA P=全局顶部导航|R=工作台_工作区_设置统一导航与用户菜单|NR=不含页面业务内容|E=component:AppTopNav|X=ui|A=导航_通知入口_账户菜单|D=vue,auth-store|S=dom -->
<template>
  <header class="app-top-nav">
    <div class="app-top-nav__inner">
      <router-link to="/home" class="brand" aria-label="返回工作台">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
            />
          </svg>
        </span>
        <span class="brand__name">Octopus AI Novel</span>
      </router-link>

      <nav class="desktop-nav" aria-label="主导航">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          :class="{ 'nav-link--active': isActive(link.to) }"
        >
          {{ link.label }}
        </router-link>
      </nav>

      <div class="nav-actions">
        <router-link v-if="authStore.user?.is_admin" to="/admin" class="admin-link">
          管理后台
        </router-link>

        <button
          type="button"
          class="icon-button"
          aria-label="查看系统更新"
          title="系统更新"
          @click="handleNotifications"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          <span v-if="notificationCount > 0" class="notification-dot" aria-hidden="true"></span>
        </button>

        <div ref="dropdownContainer" class="user-menu">
          <button
            type="button"
            class="user-trigger"
            :aria-expanded="userMenuOpen"
            aria-haspopup="menu"
            @click="userMenuOpen = !userMenuOpen"
          >
            <span class="user-avatar">{{ userInitial }}</span>
            <span class="user-name">{{ authStore.user?.username || '创作者' }}</span>
            <svg
              class="chevron"
              :class="{ 'chevron--open': userMenuOpen }"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <div v-if="userMenuOpen" class="user-dropdown" role="menu">
            <router-link to="/settings" class="dropdown-item" role="menuitem" @click="closeMenus">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
              账户设置
            </router-link>
            <div class="dropdown-divider"></div>
            <button
              type="button"
              class="dropdown-item dropdown-item--danger"
              role="menuitem"
              @click="handleLogout"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              退出登录
            </button>
          </div>
        </div>

        <button
          type="button"
          class="mobile-menu-button"
          :aria-expanded="mobileMenuOpen"
          aria-label="打开主导航"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg
            v-if="!mobileMenuOpen"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" d="M4 7h16M4 12h16M4 17h16" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </div>

    <nav v-if="mobileMenuOpen" class="mobile-nav" aria-label="移动端主导航">
      <router-link
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="mobile-nav__link"
        :class="{ 'mobile-nav__link--active': isActive(link.to) }"
        @click="closeMenus"
      >
        {{ link.label }}
      </router-link>
    </nav>
  </header>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

withDefaults(
  defineProps<{
    notificationCount?: number
  }>(),
  {
    notificationCount: 0,
  },
)

const emit = defineEmits<{
  (event: 'notification'): void
}>()

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const userMenuOpen = ref(false)
const mobileMenuOpen = ref(false)
const dropdownContainer = ref<HTMLElement | null>(null)

const links = [
  { to: '/home', label: '工作台' },
  { to: '/inspiration', label: '灵感模式' },
  { to: '/workspace', label: '我的小说' },
  { to: '/settings', label: '设置' },
]

const userInitial = computed(() => (authStore.user?.username || '创').charAt(0).toUpperCase())

const isActive = (to: string) => {
  if (to === '/home') return route.path === '/home'
  if (to === '/workspace') {
    return ['/workspace', '/detail/', '/novel/'].some((path) => route.path.startsWith(path))
  }
  return route.path.startsWith(to)
}

const closeMenus = () => {
  userMenuOpen.value = false
  mobileMenuOpen.value = false
}

const handleOutsideClick = (event: MouseEvent) => {
  if (dropdownContainer.value && !dropdownContainer.value.contains(event.target as Node)) {
    userMenuOpen.value = false
  }
}

const handleNotifications = () => {
  if (route.path === '/home') {
    emit('notification')
    return
  }
  router.push({ path: '/home', query: { updates: '1' } })
}

const handleLogout = () => {
  closeMenus()
  authStore.logout()
  router.push('/login')
}

watch(
  () => route.fullPath,
  () => closeMenus(),
)

onMounted(() => document.addEventListener('click', handleOutsideClick))
onBeforeUnmount(() => document.removeEventListener('click', handleOutsideClick))
</script>

<style scoped>
.app-top-nav {
  position: sticky;
  top: 0;
  z-index: 40;
  border-bottom: 1px solid var(--md-outline);
  background: color-mix(in srgb, var(--md-surface-dim) 88%, transparent);
  backdrop-filter: blur(14px);
}

.app-top-nav__inner {
  width: min(100% - 48px, 1440px);
  height: 72px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  color: var(--md-on-surface);
  text-decoration: none;
}

.brand__mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: var(--md-on-primary);
  background: var(--md-primary);
}

.brand__mark svg {
  width: 18px;
  height: 18px;
}

.brand__name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.desktop-nav {
  align-self: stretch;
  display: flex;
  align-items: center;
  gap: 40px;
}

.nav-link {
  position: relative;
  height: 100%;
  display: inline-flex;
  align-items: center;
  color: var(--md-on-surface-variant);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: color var(--md-duration-medium) var(--md-easing-standard);
}

.nav-link::after {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  content: '';
  background: transparent;
}

.nav-link:hover {
  color: var(--md-on-surface);
}

.nav-link--active,
.nav-link--active:hover {
  color: var(--md-primary);
}

.nav-link--active::after {
  background: var(--md-primary);
}

.nav-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

.admin-link {
  padding: 7px 10px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  color: var(--md-on-surface-variant);
  font-size: 12px;
  text-decoration: none;
  transition:
    border-color var(--md-duration-medium),
    color var(--md-duration-medium);
}

.admin-link:hover {
  border-color: color-mix(in srgb, var(--md-primary) 35%, var(--md-outline));
  color: var(--md-primary);
}

.icon-button,
.mobile-menu-button {
  position: relative;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: var(--md-radius-sm);
  display: grid;
  place-items: center;
  color: var(--md-on-surface-variant);
  background: transparent;
  transition:
    color var(--md-duration-medium),
    background var(--md-duration-medium);
}

.icon-button:hover,
.mobile-menu-button:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

.icon-button svg,
.mobile-menu-button svg {
  width: 21px;
  height: 21px;
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 6px;
  height: 6px;
  border: 1px solid var(--md-surface-dim);
  border-radius: 50%;
  background: var(--md-primary);
}

.user-menu {
  position: relative;
}

.user-trigger {
  min-height: 42px;
  padding: 5px 11px 5px 6px;
  border: 1px solid var(--md-outline);
  border-radius: 11px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--md-on-surface);
  background: var(--md-surface);
  transition:
    border-color var(--md-duration-medium),
    background var(--md-duration-medium);
}

.user-trigger:hover {
  border-color: var(--md-secondary-dark);
  background: var(--md-surface-container);
}

.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--md-on-primary);
  background: var(--md-primary);
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  font-weight: 700;
}

.user-name {
  max-width: 112px;
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  width: 15px;
  height: 15px;
  color: var(--md-on-surface-variant);
  transition: transform var(--md-duration-medium) var(--md-easing-standard);
}

.chevron--open {
  transform: rotate(180deg);
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 50;
  width: 190px;
  padding: 6px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
  box-shadow: var(--md-elevation-5);
}

.dropdown-item {
  width: 100%;
  padding: 10px;
  border: 0;
  border-radius: var(--md-radius-sm);
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--md-on-secondary-container);
  background: transparent;
  font-size: 13px;
  text-align: left;
  text-decoration: none;
  transition:
    color var(--md-duration-short),
    background var(--md-duration-short);
}

.dropdown-item:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

.dropdown-item svg {
  width: 17px;
  height: 17px;
}

.dropdown-item--danger {
  color: var(--md-error);
}

.dropdown-divider {
  height: 1px;
  margin: 5px 0;
  background: var(--md-outline);
}

.mobile-menu-button,
.mobile-nav {
  display: none;
}

@media (max-width: 900px) {
  .desktop-nav {
    display: none;
  }

  .mobile-menu-button {
    display: grid;
  }

  .mobile-nav {
    width: min(100% - 32px, 1440px);
    margin: 0 auto;
    padding: 4px 0 14px;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }

  .mobile-nav__link {
    padding: 9px 8px;
    border-radius: var(--md-radius-sm);
    color: var(--md-on-surface-variant);
    font-size: 13px;
    font-weight: 600;
    text-align: center;
    text-decoration: none;
  }

  .mobile-nav__link--active {
    color: var(--md-primary);
    background: var(--md-primary-container);
  }
}

@media (max-width: 640px) {
  .app-top-nav__inner {
    width: calc(100% - 32px);
    height: 64px;
    gap: 12px;
  }

  .brand__mark {
    width: 32px;
    height: 32px;
  }

  .brand__name,
  .admin-link,
  .user-name,
  .chevron {
    display: none;
  }

  .nav-actions {
    gap: 4px;
  }

  .user-trigger {
    min-height: 38px;
    padding: 3px;
    border-color: transparent;
    background: transparent;
  }

  .mobile-nav {
    width: calc(100% - 32px);
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
