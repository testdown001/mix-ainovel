<!-- AIMETA P=管理后台_管理员控制台|R=管理面板_子组件切换|NR=不含普通用户功能|E=route:/admin#component:AdminView|X=ui|A=管理面板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-layout has-sider class="admin-layout">
    <n-layout-sider
      collapse-mode="width"
      :collapsed="collapsed"
      :collapsed-width="64"
      :width="220"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
      class="admin-sider"
    >
      <div class="sider-header">
        <template v-if="!collapsed">
          <span class="sider-brand">管理后台</span>
          <span class="sider-role">系统管理</span>
        </template>
        <span v-else class="sider-brand-collapsed">A</span>
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
      <n-layout-header class="admin-header">
        <div class="header-left">
          <n-button
            class="mobile-trigger"
            quaternary
            circle
            size="small"
            @click="collapsed = !collapsed"
          >
            <template #icon>
              <span>☰</span>
            </template>
          </n-button>
          <span class="header-brand">管理控制台</span>
          <div class="header-metrics">
            <span class="metric"><span class="metric-dot metric-dot--ok"></span> 处理器: <b>24%</b></span>
            <span class="metric"><span class="metric-dot metric-dot--ok"></span> 内存: <b>12GB</b></span>
            <span class="metric">延迟: <b>15ms</b></span>
          </div>
        </div>
        <div class="header-right">
          <n-button size="small" type="warning" @click="goBack" class="deploy-btn">
            返回业务系统
          </n-button>
          <button class="header-icon-btn" title="通知">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"/>
            </svg>
          </button>
          <button class="header-icon-btn" title="设置">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"/>
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </button>
          <div class="header-avatar">
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path fill-rule="evenodd" d="M18.685 19.097A9.723 9.723 0 0021.75 12c0-5.385-4.365-9.75-9.75-9.75S2.25 6.615 2.25 12a9.723 9.723 0 003.065 7.097A9.716 9.716 0 0012 21.75a9.716 9.716 0 006.685-2.653zm-2.54-1.106a7.478 7.478 0 01-4.145 1.259 7.478 7.478 0 01-4.145-1.259A5.994 5.994 0 0112 15a5.994 5.994 0 014.145 3.991zM14.25 10.5a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" clip-rule="evenodd"/>
            </svg>
          </div>
        </div>
      </n-layout-header>
      <n-layout-content class="admin-content">
        <n-scrollbar class="content-scroll">
          <component :is="activeComponent" />
        </n-scrollbar>
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NScrollbar,
  type MenuOption
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

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
  | 'security'
  | 'ledger'
  | 'transactions'

const components: Record<MenuKey, ReturnType<typeof defineAsyncComponent>> = {
  statistics: defineAsyncComponent(() => import('../components/admin/Statistics.vue')),
  users: defineAsyncComponent(() => import('../components/admin/UserManagement.vue')),
  prompts: defineAsyncComponent(() => import('../components/admin/PromptManagement.vue')),
  novels: defineAsyncComponent(() => import('../components/admin/NovelManagement.vue')),
  logs: defineAsyncComponent(() => import('../components/admin/UpdateLogManagement.vue')),
  settings: defineAsyncComponent(() => import('../components/admin/SettingsManagement.vue')),
  password: defineAsyncComponent(() => import('../components/admin/PasswordManagement.vue')),
  security: defineAsyncComponent(() => import('../components/admin/SecurityCenter.vue')),
  ledger: defineAsyncComponent(() => import('../components/admin/FinancialLedger.vue')),
  transactions: defineAsyncComponent(() => import('../components/admin/TransactionManagement.vue')),
}

const renderIcon = (svg: string) => () =>
  h('svg', {
    class: 'menu-svg-icon',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '1.5',
    innerHTML: svg
  })

const menuOptions: MenuOption[] = [
  {
    key: 'statistics',
    label: '数据总览',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"/>')
  },
  {
    key: 'users',
    label: '用户管理',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>')
  },
  {
    key: 'novels',
    label: '小说项目',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>')
  },
  {
    key: 'prompts',
    label: '提示词管理',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>')
  },
  {
    key: 'logs',
    label: '系统日志',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>')
  },
  {
    key: 'settings',
    label: '系统配置',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>')
  },
  {
    key: 'password',
    label: '安全中心',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"/>')
  },
  {
    key: 'security',
    label: '防火墙监控',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.57-.598-3.75h-.152c-3.196 0-6.1-1.249-8.25-3.286zm0 13.036h.008v.008H12v-.008z"/>')
  },
  {
    key: 'ledger',
    label: '财务账本',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z"/>')
  },
  {
    key: 'transactions',
    label: '交易管理',
    icon: renderIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5"/>')
  }
]

const isMenuKey = (key: string): key is MenuKey => key in components

const syncActiveKeyWithRoute = () => {
  const tab = route.query.tab
  if (typeof tab === 'string' && isMenuKey(tab)) {
    activeKey.value = tab
  }
}

const handleMenuSelect = (key: string) => {
  if (!isMenuKey(key)) return
  activeKey.value = key
  router.replace({ name: 'admin', query: { tab: key } })
}

const activeComponent = computed(() => components[activeKey.value])

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
  () => syncActiveKeyWithRoute()
)
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}

.admin-sider {
  background-color: var(--ar-bg-surface) !important;
}

.admin-sider :deep(.n-layout-sider-scroll-container) {
  background-color: var(--ar-bg-surface);
}

.sider-header {
  height: 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 20px;
}

.sider-brand {
  font-family: var(--ar-font-display);
  font-size: 16px;
  font-weight: 700;
  font-style: italic;
  color: var(--ar-primary);
  letter-spacing: 0.02em;
}

.sider-role {
  font-family: var(--ar-font-ui);
  font-size: 10px;
  font-weight: 500;
  color: var(--ar-text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 1px;
}

.sider-brand-collapsed {
  font-family: var(--ar-font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--ar-primary);
  text-align: center;
  display: block;
}

.admin-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background-color: var(--ar-bg-base) !important;
  border-bottom: none !important;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-brand {
  font-family: var(--ar-font-display);
  font-size: 15px;
  font-weight: 600;
  font-style: italic;
  color: var(--ar-text-primary);
}

.header-metrics {
  display: flex;
  align-items: center;
  gap: 16px;
}

.metric {
  font-family: var(--ar-font-ui);
  font-size: 12px;
  color: var(--ar-text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.metric b {
  color: var(--ar-text-secondary);
}

.metric-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.metric-dot--ok {
  background: var(--ar-secondary);
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.deploy-btn {
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 600;
}

.header-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--ar-text-secondary);
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}

.header-icon-btn:hover {
  color: var(--ar-text-primary);
  background: rgba(255, 255, 255, 0.04);
}

.header-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(250, 204, 21, 0.15);
  color: #FACC15;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: 1px solid rgba(250, 204, 21, 0.3);
  transition: box-shadow 0.2s;
}

.header-avatar:hover {
  box-shadow: 0 0 10px rgba(250, 204, 21, 0.2);
}

.admin-content {
  background-color: var(--ar-bg-base) !important;
}

.content-scroll {
  height: calc(100vh - 56px);
  padding: 28px 40px;
  box-sizing: border-box;
}

.menu-svg-icon {
  width: 18px;
  height: 18px;
}

.mobile-trigger {
  display: none;
}

@media (max-width: 991px) {
  .content-scroll {
    padding: 20px 24px;
  }

  .mobile-trigger {
    display: inline-flex;
  }

  .header-metrics {
    display: none;
  }
}
</style>
