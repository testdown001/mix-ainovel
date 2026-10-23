<!-- AIMETA P=根组件_应用根节点|R=全局布局_RouterView|NR=不含页面逻辑|E=component:App|X=ui|A=RouterView|D=vue-router|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { RouterView } from 'vue-router'
import { NConfigProvider, NMessageProvider, dateZhCN, zhCN } from 'naive-ui'
import CustomAlert from '@/components/CustomAlert.vue'
import { globalAlert } from '@/composables/useAlert'
</script>

<template>
  <!-- 全站中文 locale：popconfirm 的 Cancel/Confirm、空表 No Data、分页与日期选择器此前全是英文 -->
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN">
  <n-message-provider>
    <div>
      <RouterView />

      <!-- 全局提示框 -->
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
