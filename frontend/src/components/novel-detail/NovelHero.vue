<!-- Novel Hero Card - 小说信息展示卡片 -->
<template>
  <div class="novel-hero rounded-2xl overflow-hidden">
    <!-- Background Gradient -->
    <div class="absolute inset-0 bg-gradient-to-br from-yellow-500/10 to-transparent pointer-events-none"></div>
    
    <!-- Content -->
    <div class="relative p-6 sm:p-8 flex flex-col sm:flex-row gap-6 sm:gap-8">
      <!-- Left: Info -->
      <div class="flex-1 min-w-0">
        <!-- Status Tags -->
        <div class="flex flex-wrap gap-2 mb-4">
          <span v-if="status" class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium" 
                :style="statusStyle">
            <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: statusColor }"></span>
            {{ status }}
          </span>
          <span v-for="tag in tags" :key="tag" class="px-3 py-1 rounded-full text-xs font-medium"
                style="background-color: rgba(250, 204, 21, 0.15); color: #FACC15;">
            {{ tag }}
          </span>
        </div>

        <!-- Title -->
        <h1 class="text-2xl sm:text-4xl font-bold mb-3 break-words" style="color: #F5F5F5;">
          {{ title }}
        </h1>

        <!-- Meta Info -->
        <div class="flex flex-col gap-2 text-sm" style="color: #A1A1AA;">
          <div class="flex items-center gap-2">
            <svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/>
            </svg>
            {{ author }}
          </div>
          <div class="flex items-center gap-2">
            <svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
            {{ createdDate }}
          </div>
          <div class="flex items-center gap-2">
            <svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="1"></circle>
              <path d="M12 1v6m0 6v6"></path>
            </svg>
            最近更新：{{ lastUpdated }}
          </div>
        </div>
      </div>

      <!-- Right: Progress & Action -->
      <div class="flex flex-col items-center justify-between sm:items-end gap-6">
        <!-- Progress Circle -->
        <div class="flex flex-col items-center">
          <div class="relative w-24 h-24 sm:w-28 sm:h-28">
            <svg class="w-full h-full" viewBox="0 0 120 120">
              <!-- Background circle -->
              <circle cx="60" cy="60" r="54" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="8"></circle>
              <!-- Progress circle -->
              <circle cx="60" cy="60" r="54" fill="none" stroke="#FACC15" stroke-width="8"
                      stroke-dasharray="339.29" :stroke-dashoffset="339.29 * (1 - progress / 100)"
                      stroke-linecap="round" transform="rotate(-90 60 60)"
                      style="transition: stroke-dashoffset 0.6s ease;"></circle>
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <div class="text-center">
                <div class="text-xl sm:text-2xl font-bold" style="color: #FACC15;">{{ progress }}%</div>
                <div class="text-xs" style="color: #71717A;">进度</div>
              </div>
            </div>
          </div>
          <div class="text-xs mt-2" style="color: #A1A1AA;">{{ progressText }}</div>
        </div>

        <!-- Action Button -->
        <button class="w-full sm:w-auto px-6 py-2.5 rounded-lg font-medium flex items-center justify-center gap-2"
                style="background-color: #FACC15; color: #0A0A0A;"
                @click="$emit('action')">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
          </svg>
          {{ actionLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title: string
  author: string
  createdDate: string
  lastUpdated: string
  tags?: string[]
  status?: '連載中' | '已完結' | '計劃中'
  progress: number
  progressText?: string
  actionLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  tags: () => [],
  actionLabel: '继续写作',
  progressText: ''
})

const statusColor = computed(() => {
  switch (props.status) {
    case '連載中': return '#22C55E'
    case '已完結': return '#3B82F6'
    case '計劃中': return '#F59E0B'
    default: return '#71717A'
  }
})

const statusStyle = computed(() => ({
  backgroundColor: `${statusColor.value}20`,
  color: statusColor.value
}))
</script>

<style scoped>
.novel-hero {
  position: relative;
  background: linear-gradient(135deg, rgba(250,204,21,0.05) 0%, rgba(30,30,30,0) 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background-color: #141414;
}
</style>
