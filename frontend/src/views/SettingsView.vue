<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen" style="background: #0A0A0A; color: #fff; font-family: 'Inter', sans-serif;">

    <!-- 全局导航（与入口页一致，替代此前孤立的「返回」条） -->
    <AppTopNav />

    <div class="flex max-w-5xl mx-auto px-6 py-8 gap-7">

      <!-- Sidebar -->
      <aside class="w-56 flex-shrink-0">
        <!-- User Card -->
        <div class="rounded-xl p-4 mb-4 flex items-center gap-3" style="background: #141414; border: 1px solid #2A2A2A;">
          <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold" style="background: #FFE500; color: #000;">
            {{ userInitial }}
          </div>
          <div class="min-w-0">
            <div class="text-sm font-semibold text-white truncate">{{ authStore.user?.username || '创作者' }}</div>
            <div class="text-xs truncate" style="color: #888;">
              {{ authStore.user?.is_admin ? '管理员' : '创作者' }}
            </div>
          </div>
        </div>

        <nav class="flex flex-col gap-1">
          <button
            v-for="tab in tabs" :key="tab.id"
            @click="activeTab = tab.id"
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left w-full transition-all"
            :style="activeTab === tab.id
              ? 'background-color:#2A2600; color:#FFE500;'
              : 'background-color:transparent; color:#888888;'"
            @mouseenter="e => { if(activeTab !== tab.id) { (e.currentTarget as HTMLElement).style.backgroundColor='#1C1C1C'; (e.currentTarget as HTMLElement).style.color='#fff' } }"
            @mouseleave="e => { if(activeTab !== tab.id) { (e.currentTarget as HTMLElement).style.backgroundColor='transparent'; (e.currentTarget as HTMLElement).style.color='#888888' } }"
          >
            <span v-html="tab.icon" class="w-4 h-4 flex-shrink-0"></span>
            {{ tab.label }}
          </button>
        </nav>
      </aside>

      <!-- Content -->
      <main class="flex-1 min-w-0">
        <WritingPreferences v-if="activeTab === 'writing'" />
        <SubscriptionPanel v-else-if="activeTab === 'subscription'" />
        <CreditLedger v-else-if="activeTab === 'credits'" />
        <ReferralPanel v-else-if="activeTab === 'referral'" />
        <div v-else-if="activeTab === 'admin'" class="flex flex-col items-center justify-center py-16 gap-4">
          <div class="w-14 h-14 rounded-2xl flex items-center justify-center" style="background: rgba(255,229,0,0.1);">
            <svg class="w-7 h-7" style="color:#FFE500;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <p class="text-sm" style="color:#888;">即将跳转到管理后台…</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import WritingPreferences from '@/components/WritingPreferences.vue'
import SubscriptionPanel from '@/components/SubscriptionPanel.vue'
import CreditLedger from '@/components/CreditLedger.vue'
import ReferralPanel from '@/components/ReferralPanel.vue'
import AppTopNav from '@/components/shared/AppTopNav.vue'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const userInitial = computed(() => {
  const name = authStore.user?.username || ''
  return name.charAt(0).toUpperCase() || 'U'
})

type TabId = 'writing' | 'subscription' | 'credits' | 'referral' | 'admin'

// 支持 /settings?tab=subscription 直达（升级引导/定价页跳转的落点）
const VALID_QUERY_TABS: TabId[] = ['writing', 'subscription', 'credits', 'referral']
const tabFromQuery = (): TabId | null => {
  const t = String(route.query.tab || '')
  return (VALID_QUERY_TABS as string[]).includes(t) ? (t as TabId) : null
}

const activeTab = ref<TabId>(tabFromQuery() || 'writing')

watch(
  () => route.query.tab,
  () => {
    const t = tabFromQuery()
    if (t) activeTab.value = t
  },
)

watch(activeTab, (val) => {
  if (val === 'admin') {
    router.push('/admin')
  }
})

const isAdmin = computed(() => authStore.user?.is_admin === true)

const baseTabs: Array<{ id: TabId; label: string; icon: string }> = [
  {
    id: 'writing',
    label: '写作偏好',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>',
  },
  {
    id: 'subscription',
    label: '会员套餐',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>',
  },
  {
    id: 'credits',
    label: '积分明细',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path stroke-linecap="round" stroke-linejoin="round" d="M14.5 9.5a2.5 2.5 0 00-2.5-1.5c-1.4 0-2.5.9-2.5 2s1.1 2 2.5 2 2.5.9 2.5 2-1.1 2-2.5 2a2.5 2.5 0 01-2.5-1.5M12 6.5v11"/></svg>',
  },
  {
    id: 'referral',
    label: '邀请返积分',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 9v6m3-3h-6M15 7a4 4 0 11-8 0 4 4 0 018 0zM3 20a7 7 0 0113-3.7"/></svg>',
  },
]

const adminTab: { id: TabId; label: string; icon: string } = {
  id: 'admin',
  label: '管理后台',
  icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
}

const tabs = computed(() => isAdmin.value ? [...baseTabs, adminTab] : baseTabs)
</script>
