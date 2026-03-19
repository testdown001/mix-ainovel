<!-- Statistics Card - 统计数据卡片 -->
<template>
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
    <div v-for="stat in statistics" :key="stat.key" 
         class="stat-card p-4 sm:p-5 rounded-xl border"
         style="border-color: rgba(255, 255, 255, 0.06); background-color: #141414;">
      <!-- Icon -->
      <div class="mb-3">
        <component :is="stat.icon" class="w-5 h-5 sm:w-6 sm:h-6" 
                   :style="{ color: stat.color }"/>
      </div>
      
      <!-- Value -->
      <div class="text-xl sm:text-2xl font-bold mb-1" style="color: #F5F5F5;">
        {{ stat.value }}
      </div>
      
      <!-- Label -->
      <div class="text-xs sm:text-sm" style="color: #A1A1AA;">
        {{ stat.label }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'

interface Statistic {
  key: string
  label: string
  value: string | number
  color?: string
  icon?: any
}

interface Props {
  statistics: Statistic[]
}

defineProps<Props>()

// Default icons
const defaultIcons = {
  words: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { d: 'M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z' })
  ]),
  chapters: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }),
    h('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' })
  ]),
  quality: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('path', { d: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z' })
  ]),
  rating: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })
  ])
}
</script>

<style scoped>
.stat-card {
  transition: all 0.2s ease;
}

.stat-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background-color: #1a1a1a;
}
</style>
