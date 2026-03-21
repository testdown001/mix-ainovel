<!-- AIMETA P=管理后台_管理员控制台|R=管理面板_子组件切换|NR=不含普通用户功能|E=route:/admin#component:AdminView|X=ui|A=管理面板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-layout has-sider class="admin-layout">
      <n-layout-sider
        collapse-mode="width"
        :collapsed="collapsed"
        :collapsed-width="64"
        :width="240"
        bordered
        show-trigger
        @collapse="collapsed = true"
        @expand="collapsed = false"
      >
        <div class="sider-header">
          <span class="logo" v-if="!collapsed">
            <span class="logo-accent">✦</span> Arboris 管理台
          </span>
          <span class="logo-small" v-else>管理</span>
        </div>
        <n-menu
          :value="activeKey"
          :options="menuOptions"
          :collapsed="collapsed"
          :collapsed-width="64"
          :accordion="true"
          @update:value="handleMenuSelect"
        />
      </n-layout-sider>

      <n-layout>
        <n-layout-header bordered class="admin-header">
          <n-space align="center" justify="space-between" class="header-content">
            <n-space align="center" :size="12">
              <n-button
                class="mobile-trigger"
                quaternary
                circle
                size="small"
                @click="collapsed = !collapsed"
              >
                <template #icon>
                  <span class="icon">☰</span>
                </template>
              </n-button>
              <span class="header-title">{{ currentMenuLabel }}</span>
            </n-space>
            <n-space align="center" :size="10">
              <span class="header-subtitle">高效掌控平台运行状态</span>
              <n-button size="small" @click="goBack" class="back-btn">
                返回业务系统
              </n-button>
            </n-space>
          </n-space>
        </n-layout-header>
        <n-layout-content class="admin-content">
          <n-scrollbar class="content-scroll">
            <component :is="activeComponent" />
          </n-scrollbar>
        </n-layout-content>
      </n-layout>
    </n-layout>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NConfigProvider,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NScrollbar,
  NSpace,
  darkTheme,
  type GlobalThemeOverrides,
  type MenuOption
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#FFE500',
    primaryColorHover: '#FFF176',
    primaryColorPressed: '#F9C800',
    primaryColorSuppl: '#FFE500',
    bodyColor: '#0A0A0A',
    baseColor: '#0A0A0A',
    cardColor: '#141414',
    modalColor: '#141414',
    popoverColor: '#1C1C1C',
    tableColor: '#141414',
    tableColorHover: '#1C1C1C',
    inputColor: '#1C1C1C',
    inputColorDisabled: '#111',
    borderColor: '#2A2A2A',
    dividerColor: '#2A2A2A',
    hoverColor: '#1C1C1C',
    textColorBase: '#FFFFFF',
    textColor1: '#FFFFFF',
    textColor2: '#CCCCCC',
    textColor3: '#888888',
    placeholderColor: '#555555',
    tagColor: '#1C1C1C',
    scrollbarColor: '#2A2A2A',
    scrollbarColorHover: '#444444'
  },
  Button: {
    textColorPrimary: '#000000',
    textColorHoverPrimary: '#000000',
    textColorPressedPrimary: '#000000',
    textColorFocusPrimary: '#000000'
  },
  Menu: {
    color: '#141414',
    itemColorActive: 'rgba(255,229,0,0.12)',
    itemColorActiveHover: 'rgba(255,229,0,0.18)',
    itemTextColorActive: '#FFE500',
    itemIconColorActive: '#FFE500',
    itemTextColorActiveHover: '#FFE500',
    itemIconColorActiveHover: '#FFE500',
    itemColorHover: 'rgba(255,255,255,0.05)'
  },
  Layout: {
    siderColor: '#141414',
    headerColor: '#141414',
    color: '#0A0A0A'
  },
  Switch: {
    railColorActive: '#FFE500'
  },
  Tag: {
    colorInfo: 'rgba(255,229,0,0.15)',
    textColorInfo: '#FFE500',
    colorSuccess: 'rgba(46,213,115,0.15)',
    textColorSuccess: '#2ED573',
    colorError: 'rgba(255,71,87,0.15)',
    textColorError: '#FF4757'
  }
}

const collapsed = ref(false)
const activeKey = ref<MenuKey>('statistics')
const router = useRouter()
const route = useRoute()

type MenuKey =
  | 'statistics'
  | 'users'
  | 'prompts'
  | 'novels'
  | 'logs'
  | 'settings'
  | 'password'

const components: Record<MenuKey, ReturnType<typeof defineAsyncComponent>> = {
  statistics: defineAsyncComponent(() => import('../components/admin/Statistics.vue')),
  users: defineAsyncComponent(() => import('../components/admin/UserManagement.vue')),
  prompts: defineAsyncComponent(() => import('../components/admin/PromptManagement.vue')),
  novels: defineAsyncComponent(() => import('../components/admin/NovelManagement.vue')),
  logs: defineAsyncComponent(() => import('../components/admin/UpdateLogManagement.vue')),
  settings: defineAsyncComponent(() => import('../components/admin/SettingsManagement.vue')),
  password: defineAsyncComponent(() => import('../components/admin/PasswordManagement.vue'))
}

const iconRenderers: Record<MenuKey, () => any> = {
  statistics: () => h('span', { class: 'menu-icon' }, '📊'),
  users: () => h('span', { class: 'menu-icon' }, '👤'),
  prompts: () => h('span', { class: 'menu-icon' }, '🗒️'),
  novels: () => h('span', { class: 'menu-icon' }, '📚'),
  logs: () => h('span', { class: 'menu-icon' }, '📝'),
  settings: () => h('span', { class: 'menu-icon' }, '⚙️'),
  password: () => h('span', { class: 'menu-icon' }, '🔒')
}

const menuOptions: MenuOption[] = [
  { key: 'statistics', label: '数据总览', icon: iconRenderers.statistics },
  { key: 'users', label: '用户管理', icon: iconRenderers.users },
  { key: 'prompts', label: '提示词管理', icon: iconRenderers.prompts },
  { key: 'novels', label: '小说项目', icon: iconRenderers.novels },
  { key: 'logs', label: '更新日志', icon: iconRenderers.logs },
  { key: 'settings', label: '系统配置', icon: iconRenderers.settings },
  { key: 'password', label: '安全中心', icon: iconRenderers.password }
]

const isMenuKey = (key: string): key is MenuKey => key in components

const syncActiveKeyWithRoute = () => {
  const tab = route.query.tab
  if (typeof tab === 'string' && isMenuKey(tab)) {
    activeKey.value = tab
  }
}

const handleMenuSelect = (key: string) => {
  if (!isMenuKey(key)) {
    return
  }
  activeKey.value = key
  router.replace({ name: 'admin', query: { tab: key } })
}

const activeComponent = computed(() => components[activeKey.value])
const currentMenuLabel = computed(() => {
  const match = menuOptions.find((option) => option.key === activeKey.value)
  return match ? (match.label as string) : ''
})

const goBack = () => {
  router.push('/')
}

const updateCollapsedByWidth = () => {
  collapsed.value = window.innerWidth < 992
}

onMounted(() => {
  updateCollapsedByWidth()
  window.addEventListener('resize', updateCollapsedByWidth)
  syncActiveKeyWithRoute()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateCollapsedByWidth)
})

watch(
  () => route.query.tab,
  () => {
    syncActiveKeyWithRoute()
  }
)
</script>

<style scoped>
.admin-layout {
  height: 100vh;
  background: #0A0A0A;
}

.sider-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: #FFFFFF;
  border-bottom: 1px solid #2A2A2A;
  padding: 0 12px;
  font-family: 'Space Grotesk', sans-serif;
}

.logo {
  font-size: 1rem;
  white-space: nowrap;
  color: #FFFFFF;
}

.logo-accent {
  color: #FFE500;
}

.logo-small {
  font-size: 0.875rem;
  color: #FFE500;
  font-weight: 700;
}

.admin-header {
  background: #141414 !important;
  border-bottom: 1px solid #2A2A2A !important;
  padding: 0 20px;
}

.header-content {
  width: 100%;
  height: 60px;
}

.header-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #FFFFFF;
  font-family: 'Space Grotesk', sans-serif;
}

.header-subtitle {
  font-size: 0.875rem;
  color: #888888;
}

.back-btn {
  border: 1px solid #2A2A2A !important;
  color: #CCCCCC !important;
  background: transparent !important;
}

.back-btn:hover {
  border-color: #FFE500 !important;
  color: #FFE500 !important;
}

.admin-content {
  background: #0A0A0A !important;
}

.content-scroll {
  height: calc(100vh - 60px);
  padding: 24px;
  box-sizing: border-box;
}

.menu-icon {
  font-size: 1.1rem;
}

.mobile-trigger {
  display: none;
}

@media (max-width: 991px) {
  .content-scroll {
    padding: 16px;
  }

  .mobile-trigger {
    display: inline-flex;
  }

  .header-content {
    flex-direction: column;
    align-items: stretch;
    gap: 12px !important;
  }

  .header-subtitle {
    font-size: 0.85rem;
  }
}
</style>
