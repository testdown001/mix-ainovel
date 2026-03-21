<!-- AIMETA P=项目卡片_小说项目展示|R=项目信息卡片|NR=不含编辑功能|E=component:ProjectCard|X=internal|A=卡片组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div
    class="group flex flex-col justify-between cursor-pointer transition-all duration-200"
    style="background: #141414; border: 1px solid #1C1C1C; border-radius: 18px; padding: 22px; min-height: 200px;"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
    :style="{ borderColor: hovered ? '#2A2A2A' : '#1C1C1C' }"
  >
    <div>
      <!-- Header: Icon + Title -->
      <div class="flex items-start gap-4 mb-4">
        <div
          class="flex-shrink-0 flex items-center justify-center rounded-xl"
          style="width: 46px; height: 46px; font-size: 22px;"
          :style="{ background: genreColor.bg }"
        >
          {{ genreIcon }}
        </div>
        <div class="flex-1 min-w-0 cursor-pointer" @click="$emit('detail', project.id)">
          <h3 class="font-bold truncate hover:opacity-80 transition-opacity" style="color: #fff; font-size: 16px; font-family: 'Space Grotesk', sans-serif; margin-bottom: 4px;">
            {{ project.title }}
          </h3>
          <div class="flex items-center gap-2 flex-wrap">
            <span v-if="project.genre" style="background: #FFE500; color: #000; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px;">
              {{ project.genre }}
            </span>
            <span style="color: #888; font-size: 12px;">{{ getStatusText }}</span>
          </div>
          <p style="color: #555; font-size: 11px; margin-top: 4px;">
            最后编辑: {{ formatDateTime(project.last_edited) }}
          </p>
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="mb-4">
        <div class="flex justify-between mb-2">
          <span style="color: #888; font-size: 12px;">完成进度</span>
          <span style="color: #fff; font-size: 12px; font-weight: 600;">{{ progress }}%</span>
        </div>
        <div style="height: 5px; background: #2A2A2A; border-radius: 999px; overflow: hidden;">
          <div
            style="height: 100%; border-radius: 999px; transition: width 0.4s ease;"
            :style="{ width: `${progress}%`, background: '#FFE500' }"
          ></div>
        </div>
      </div>

      <!-- Chips -->
      <div class="flex flex-wrap gap-2">
        <span
          v-if="chapterCount > 0"
          class="flex items-center gap-1"
          style="background: #1C1C1C; border: 1px solid #2A2A2A; color: #888; font-size: 12px; padding: 3px 10px; border-radius: 999px;"
        >
          <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {{ chapterCount }} 章节
        </span>
      </div>
    </div>

    <!-- Action Buttons — always visible -->
    <div class="flex gap-2 mt-5">
      <button
        @click.stop="$emit('detail', project.id)"
        class="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-medium transition-colors"
        style="background: #1C1C1C; border: 1px solid #2A2A2A; color: #888; cursor: pointer;"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
        查看
      </button>
      <button
        @click.stop="handleDelete"
        class="flex items-center justify-center rounded-xl transition-colors"
        style="width: 38px; height: 38px; background: #1C1C1C; border: 1px solid #2A2A2A; color: #FF4757; cursor: pointer;"
        title="删除项目"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
      <button
        @click.stop="$emit('continue', project)"
        class="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-bold transition-colors"
        style="background: #FFE500; color: #000; border: none; cursor: pointer;"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
        创作
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NovelProjectSummary } from '@/api/novel'
import { formatDateTime } from '@/utils/date'

interface Props {
  project: NovelProjectSummary
}

const props = defineProps<Props>()
const hovered = ref(false)

const emit = defineEmits<{
  (e: 'click', id: string): void
  (e: 'detail', id: string): void
  (e: 'continue', project: NovelProjectSummary): void
  (e: 'delete', id: string): void
}>()

const GENRE_ICONS: Record<string, string> = {
  '玄幻': '⚔️', '武侠': '🗡️', '科幻': '🚀', '悬疑': '🔍',
  '都市': '🏙️', '历史': '🏯', '言情': '💕', '奇幻': '🌟',
  '末世': '💀', '仙侠': '☁️', '穿越': '⏳', '东方': '🎋',
}

const genreIcon = computed(() => {
  const g = props.project.genre || ''
  for (const [key, icon] of Object.entries(GENRE_ICONS)) {
    if (g.includes(key)) return icon
  }
  return '📖'
})

const genreColor = computed(() => {
  const g = props.project.genre || ''
  if (g.includes('科幻') || g.includes('悬疑')) return { bg: '#0A1A2A' }
  if (g.includes('奇幻') || g.includes('冒险')) return { bg: '#0A2A1A' }
  if (g.includes('穿越') || g.includes('言情')) return { bg: '#2A0A0A' }
  if (g.includes('东方') || g.includes('武侠')) return { bg: '#2A2600' }
  return { bg: '#1C1C1C' }
})

const progress = computed(() => {
  const { completed_chapters, total_chapters } = props.project
  return total_chapters > 0 ? Math.round((completed_chapters / total_chapters) * 100) : 0
})

const getStatusText = computed(() => {
  const { completed_chapters, total_chapters } = props.project
  if (completed_chapters > 0) {
    return `已完成 ${completed_chapters}/${total_chapters} 章`
  } else if (total_chapters > 0) {
    return '准备创作'
  } else {
    return '蓝图完成'
  }
})

const chapterCount = computed(() => {
  return props.project.total_chapters
})

const handleDelete = () => {
  emit('delete', props.project.id)
}
</script>
