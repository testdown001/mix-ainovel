<!-- AIMETA P=根组件_应用根节点|R=全局布局_RouterView|NR=不含页面逻辑|E=component:App|X=ui|A=RouterView|D=vue-router|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { NMessageProvider, NConfigProvider, darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import CustomAlert from '@/components/CustomAlert.vue'
import AppNavbar from '@/components/shared/AppNavbar.vue'
import { globalAlert } from '@/composables/useAlert'

const route = useRoute()

const hideNavbarRoutes = new Set(['login', 'register', 'writing-desk'])
const showNavbar = computed(() => {
  const name = route.name as string | undefined
  return name && !hideNavbarRoutes.has(name)
})

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#FACC15',
    primaryColorHover: '#EAB308',
    primaryColorPressed: '#CA8A04',
    primaryColorSuppl: '#FDE047',
    bodyColor: '#0A0A0A',
    cardColor: '#141414',
    modalColor: '#1C1C1C',
    popoverColor: '#1C1C1C',
    inputColor: '#1C1C1C',
    tableColor: '#141414',
    textColorBase: '#F5F5F5',
    textColor1: '#F5F5F5',
    textColor2: '#A1A1AA',
    textColor3: '#71717A',
    borderColor: 'rgba(255, 255, 255, 0.08)',
    dividerColor: 'rgba(255, 255, 255, 0.06)',
    hoverColor: 'rgba(255, 255, 255, 0.05)',
    pressedColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: '12px',
    borderRadiusSmall: '8px',
    fontFamily: "'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: '14px',
    heightMedium: '44px',
    heightSmall: '36px',
    heightLarge: '48px',
    successColor: '#22C55E',
    successColorHover: '#16A34A',
    successColorPressed: '#15803D',
    errorColor: '#EF4444',
    errorColorHover: '#DC2626',
    errorColorPressed: '#B91C1C',
    warningColor: '#F59E0B',
    warningColorHover: '#D97706',
    warningColorPressed: '#B45309',
    infoColor: '#3B82F6',
    infoColorHover: '#2563EB',
    infoColorPressed: '#1D4ED8',
  },
  Button: {
    borderRadiusMedium: '9999px',
    borderRadiusSmall: '9999px',
    borderRadiusLarge: '9999px',
    fontWeightStrong: '600',
    textColorPrimary: '#0A0A0A',
    textColorHoverPrimary: '#0A0A0A',
    textColorPressedPrimary: '#0A0A0A',
  },
  Card: {
    borderRadius: '16px',
    borderColor: 'rgba(255, 255, 255, 0.06)',
    color: '#141414',
  },
  Input: {
    borderRadius: '12px',
    color: '#1C1C1C',
    colorFocus: '#1C1C1C',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderHover: '1px solid rgba(255, 255, 255, 0.15)',
    borderFocus: '1px solid #FACC15',
    boxShadowFocus: '0 0 0 3px rgba(250, 204, 21, 0.1)',
  },
  Tag: {
    borderRadius: '9999px',
  },
  Dialog: {
    borderRadius: '24px',
    color: '#1C1C1C',
  },
  Message: {
    borderRadius: '12px',
  },
  Tabs: {
    tabTextColorActiveLine: '#FACC15',
    tabTextColorHoverLine: '#F5F5F5',
    tabTextColorLine: '#71717A',
    barColor: '#FACC15',
  },
}
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <div class="min-h-screen flex flex-col">
        <AppNavbar v-if="showNavbar" />
        <RouterView class="flex-1" />

        <CustomAlert
          v-for="alert in globalAlert.alerts.value"
          :key="alert.id"
          :visible="alert.visible"
          :type="alert.type"
          :title="alert.title"
          :message="alert.message"
          :show-cancel="alert.showCancel"
          :confirm-text="alert.confirmText"
          :cancel-text="alert.cancelText"
          @confirm="globalAlert.closeAlert(alert.id, true)"
          @cancel="globalAlert.closeAlert(alert.id, false)"
          @close="globalAlert.closeAlert(alert.id, false)"
        />
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
</style>
