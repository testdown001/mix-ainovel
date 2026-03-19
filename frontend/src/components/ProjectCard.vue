<!-- AIMETA P=项目卡片_小说项目展示|R=项目信息卡片|NR=不含编辑功能|E=component:ProjectCard|X=internal|A=卡片组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="pc-card group">
    <div>
      <!-- Header: Icon + Title -->
      <div class="flex items-center gap-4 mb-4">
        <div class="pc-icon-box" :style="{ borderColor: genreAccent + '30' }">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
            :style="{ color: genreAccent }"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
            />
          </svg>
        </div>
        <div class="flex-1 cursor-pointer" @click="$emit('detail', project.id)">
          <h3 class="pc-title">
            {{ project.title }}
          </h3>
          <p class="pc-meta">
            {{ project.genre || '未知类型' }} · {{ getStatusText }}
          </p>
          <p class="pc-timestamp">
            最后编辑: {{ formatDateTime(project.last_edited) }}
          </p>
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="mb-4">
        <div class="flex justify-between mb-2">
          <span class="pc-progress-label">完成进度</span>
          <span class="pc-progress-value">{{ progress }}%</span>
        </div>
        <div class="pc-progress-track">
          <div 
            class="pc-progress-bar" 
            :style="{ width: `${progress}%`, backgroundColor: genreAccent }"
          ></div>
        </div>
      </div>

      <!-- Genre / Chapter Chips -->
      <div class="flex flex-wrap gap-2 mb-4">
        <span 
          v-if="project.genre"
          class="pc-chip"
          :style="{ backgroundColor: genreAccent + '12', color: genreAccent, borderColor: genreAccent + '25' }"
        >
          {{ project.genre }}
        </span>
        <span 
          v-if="chapterCount > 0"
          class="pc-chip pc-chip--neutral"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {{ chapterCount }} 章节
        </span>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="pc-actions">
      <button
        @click.stop="$emit('detail', project.id)"
        class="pc-btn pc-btn--tonal flex-1"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
        查看
      </button>
      <button
        @click.stop="handleDelete"
        class="pc-btn pc-btn--danger"
        title="删除项目"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
      <button
        @click.stop="$emit('continue', project)"
        class="pc-btn pc-btn--primary flex-1"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
        创作
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NovelProjectSummary } from '@/api/novel'
import { formatDateTime } from '@/utils/date'

interface Props {
  project: NovelProjectSummary
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'click', id: string): void
  (e: 'detail', id: string): void
  (e: 'continue', project: NovelProjectSummary): void
  (e: 'delete', id: string): void
}>()

const genreAccent = computed(() => {
  const genre = props.project.genre || ''
  
  if (genre.includes('科幻') || genre.includes('悬疑')) return '#60A5FA'
  if (genre.includes('奇幻') || genre.includes('冒险')) return '#4ADE80'
  if (genre.includes('穿越') || genre.includes('言情')) return '#F87171'
  if (genre.includes('东方') || genre.includes('武侠')) return '#FACC15'
  
  return '#FACC15'
})

// 使用后端预计算的进度数据
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

// 使用后端返回的预计算数据
const chapterCount = computed(() => {
  return props.project.total_chapters
})

const handleDelete = () => {
  emit('delete', props.project.id)
}
</script>

<style scoped>
.pc-card {
  background-color: #0f1419;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: border-color 0.25s, box-shadow 0.3s;
  font-family: var(--ar-font-ui);
}

.pc-card:hover {
  border-color: rgba(250, 204, 21, 0.2);
  box-shadow: 0 0 24px rgba(250, 204, 21, 0.06);
}

.pc-icon-box {
  width: 3rem;
  height: 3rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #171c22;
  border: 1px solid rgba(77, 70, 50, 0.15);
  transition: border-color 0.2s;
}

.pc-title {
  font-family: var(--ar-font-display);
  font-size: 1.05rem;
  font-weight: 600;
  color: #dee3eb;
  line-height: 1.4;
  letter-spacing: 0.01em;
  transition: color 0.2s;
  cursor: pointer;
}

.pc-title:hover {
  color: #FACC15;
}

.pc-meta {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  color: #8b929a;
  margin-top: 0.1rem;
}

.pc-timestamp {
  font-family: var(--ar-font-ui);
  font-size: 0.7rem;
  color: #545d68;
  margin-top: 0.2rem;
}

/* Progress */
.pc-progress-label {
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  font-weight: 500;
  color: #8b929a;
}

.pc-progress-value {
  font-family: var(--ar-font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: #dee3eb;
}

.pc-progress-track {
  width: 100%;
  height: 3px;
  background-color: #252a30;
  border-radius: 2px;
  overflow: hidden;
}

.pc-progress-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
  box-shadow: 0 0 8px rgba(250, 204, 21, 0.15);
}

/* Chips */
.pc-chip {
  font-family: var(--ar-font-ui);
  font-size: 0.7rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  border: 1px solid;
  letter-spacing: 0.02em;
}

.pc-chip--neutral {
  background-color: #171c22;
  color: #8b929a;
  border-color: rgba(77, 70, 50, 0.15);
}

/* Action buttons */
.pc-actions {
  display: flex;
  gap: 0.5rem;
  opacity: 0;
  transition: opacity 0.25s, transform 0.25s;
  transform: translateY(0.5rem);
}

.group:hover .pc-actions {
  opacity: 1;
  transform: translateY(0);
}

.pc-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  padding: 0.4rem 0.75rem;
  border-radius: 4px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s, color 0.2s;
}

.pc-btn--tonal {
  background-color: #171c22;
  color: #8b929a;
  border-color: rgba(77, 70, 50, 0.15);
}

.pc-btn--tonal:hover {
  color: #dee3eb;
  border-color: rgba(77, 70, 50, 0.3);
  background-color: #252a30;
}

.pc-btn--primary {
  background-color: rgba(250, 204, 21, 0.1);
  color: #FACC15;
  border-color: rgba(250, 204, 21, 0.3);
}

.pc-btn--primary:hover {
  background-color: rgba(250, 204, 21, 0.18);
  border-color: rgba(250, 204, 21, 0.5);
  box-shadow: 0 0 12px rgba(250, 204, 21, 0.08);
}

.pc-btn--danger {
  background: transparent;
  color: #545d68;
  border-color: rgba(77, 70, 50, 0.15);
  padding: 0.4rem;
}

.pc-btn--danger:hover {
  color: #EF4444;
  border-color: rgba(239, 68, 68, 0.3);
  background-color: rgba(239, 68, 68, 0.06);
}
</style>
