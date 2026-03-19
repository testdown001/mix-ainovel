<!-- AIMETA P=根组件_应用根节点|R=全局布局_RouterView|NR=不含页面逻辑|E=component:App|X=ui|A=RouterView|D=vue-router|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { NMessageProvider, NConfigProvider, darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import CustomAlert from '@/components/CustomAlert.vue'
import AppNavbar from '@/components/shared/AppNavbar.vue'
import { globalAlert } from '@/composables/useAlert'

const route = useRoute()

const hideNavbarRoutes = new Set(['login', 'register', 'writing-desk', 'admin', 'mind-map'])
const showNavbar = computed(() => {
  const name = route.name as string | undefined
  return name && !hideNavbarRoutes.has(name)
})

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#FACC15',
    primaryColorHover: '#eec200',
    primaryColorPressed: '#CA8A04',
    primaryColorSuppl: '#FDE047',
    bodyColor: '#000000',
    cardColor: '#0f1419',
    modalColor: '#171c22',
    popoverColor: '#171c22',
    inputColor: '#171c22',
    tableColor: '#0f1419',
    tableHeaderColor: '#171c22',
    textColorBase: '#dee3eb',
    textColor1: '#dee3eb',
    textColor2: '#8b929a',
    textColor3: '#545d68',
    borderColor: 'rgba(77, 70, 50, 0.15)',
    dividerColor: 'rgba(77, 70, 50, 0.1)',
    hoverColor: 'rgba(255, 255, 255, 0.04)',
    pressedColor: 'rgba(255, 255, 255, 0.06)',
    borderRadius: '4px',
    borderRadiusSmall: '4px',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: '14px',
    heightMedium: '44px',
    heightSmall: '36px',
    heightLarge: '48px',
    successColor: '#4ADE80',
    successColorHover: '#22C55E',
    successColorPressed: '#16A34A',
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
    borderRadiusMedium: '4px',
    borderRadiusSmall: '4px',
    borderRadiusLarge: '4px',
    fontWeightStrong: '600',
    textColorPrimary: '#000000',
    textColorHoverPrimary: '#000000',
    textColorPressedPrimary: '#000000',
  },
  Card: {
    borderRadius: '4px',
    borderColor: 'rgba(77, 70, 50, 0.15)',
    color: '#0f1419',
  },
  Input: {
    borderRadius: '4px',
    color: '#171c22',
    colorFocus: '#171c22',
    border: '1px solid rgba(77, 70, 50, 0.15)',
    borderHover: '1px solid rgba(77, 70, 50, 0.3)',
    borderFocus: '1px solid #4ADE80',
    boxShadowFocus: '0 0 0 2px rgba(74, 222, 128, 0.1)',
  },
  Tag: {
    borderRadius: '2px',
  },
  Dialog: {
    borderRadius: '4px',
    color: '#171c22',
  },
  Message: {
    borderRadius: '4px',
  },
  Tabs: {
    tabTextColorActiveLine: '#FACC15',
    tabTextColorHoverLine: '#dee3eb',
    tabTextColorLine: '#545d68',
    barColor: '#FACC15',
    tabFontWeightActive: '600',
  },
  DataTable: {
    borderRadius: '4px',
    thColor: '#171c22',
    tdColor: '#0f1419',
    tdColorHover: '#171c22',
    borderColor: 'rgba(77, 70, 50, 0.1)',
  },
  Menu: {
    borderRadius: '4px',
    itemTextColorActive: '#FACC15',
    itemTextColorActiveHover: '#FACC15',
    itemIconColorActive: '#FACC15',
    itemIconColorActiveHover: '#FACC15',
    itemColorActive: 'rgba(250, 204, 21, 0.1)',
    itemColorActiveHover: 'rgba(250, 204, 21, 0.15)',
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: '4px',
      },
    },
  },
  Slider: {
    fillColor: '#FACC15',
    fillColorHover: '#eec200',
  },
  Switch: {
    railColorActive: '#4ADE80',
  },
  Notification: {
    borderRadius: '4px',
    color: '#171c22',
  },
  Tooltip: {
    borderRadius: '4px',
    color: '#252a30',
  },
  Dropdown: {
    borderRadius: '4px',
    color: '#171c22',
    optionColorHover: 'rgba(255, 255, 255, 0.04)',
  },
  Popover: {
    borderRadius: '4px',
    color: '#171c22',
  },
  Modal: {
    borderRadius: '4px',
    color: '#171c22',
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
