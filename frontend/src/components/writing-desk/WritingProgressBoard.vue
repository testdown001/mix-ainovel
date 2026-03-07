<!-- AIMETA P=写作进度看板_实时进度展示|R=进度看板_阶段展示_干预按钮|NR=|E=WritingProgressBoard|X=internal|A=进度可视化|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="writing-progress-board">
    <!-- 头部信息 -->
    <div class="board-header">
      <div class="header-left">
        <h3 class="chapter-title">
          <span class="chapter-badge">第 {{ progress?.chapter_number }} 章</span>
          {{ progress?.chapter_title || '加载中...' }}
        </h3>
      </div>
      <div class="header-right">
        <span class="status-badge" :class="statusClass">
          {{ statusText }}
        </span>
        <span class="elapsed-time" v-if="progress?.started_at && progress.status !== 'completed'">
          已进行 {{ formatElapsedTime(progress.elapsed_seconds) }}
        </span>
      </div>
    </div>

    <!-- 阶段流转图 -->
    <div class="stage-flow">
      <div 
        v-for="(stage, index) in progress?.stages" 
        :key="stage.stage"
        class="stage-node"
        :class="[
          stage.status, 
          { active: isStageActive(stage) }
        ]"
      >
        <div class="stage-connector" v-if="index > 0"></div>
        <div class="stage-icon">
          <span v-if="stage.status === 'completed'">✅</span>
          <span v-else-if="stage.status === 'running'">🔄</span>
          <span v-else-if="stage.status === 'failed'">❌</span>
          <span v-else-if="stage.status === 'paused'">⏸️</span>
          <span v-else>{{ stage.display?.icon || '⬜' }}</span>
        </div>
        <div class="stage-content">
          <div class="stage-name">{{ stage.display?.name || stage.stage }}</div>
          <div class="stage-message" v-if="stage.message">{{ stage.message }}</div>
          <div class="stage-progress-bar" v-if="stage.status === 'running'">
            <div class="progress-fill" :style="{ width: stage.progress + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 实时预览 -->
    <div class="live-preview" v-if="progress?.last_output_preview">
      <div class="preview-header">
        <span class="preview-label">📝 实时草稿预览</span>
      </div>
      <div class="preview-content">
        {{ progress.last_output_preview }}
      </div>
    </div>

    <!-- 干预面板 -->
    <div class="intervention-panel" v-if="progress?.can_intervene && progress.status === 'running'">
      <span class="intervention-label">⚡ 干预操作</span>
      <div class="intervention-buttons">
        <button class="btn-intervene btn-pause" @click="handlePause" :disabled="isPausing">
          ⏸ 暂停
        </button>
        <button class="btn-intervene btn-adjust" @click="$emit('adjust')">
          🎯 调整方向
        </button>
        <button class="btn-intervene btn-supplement" @click="$emit('supplement')">
          📝 补充设定
        </button>
        <button class="btn-intervene btn-stop" @click="$emit('stop')">
          ⏹ 终止
        </button>
      </div>
    </div>

    <!-- 暂停状态显示 -->
    <div class="paused-notice" v-if="progress?.status === 'paused'">
      <span>⏸️ 写作已暂停</span>
      <button class="btn-resume" @click="handleResume">▶️ 继续写作</button>
    </div>

    <!-- 完成状态 -->
    <div class="completed-notice" v-if="progress?.status === 'completed'">
      <span>✅ 章节生成完成！</span>
      <button class="btn-view" @click="$emit('view')">查看结果</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import type { WritingProgress } from '@/api/writingProgress'
import { connectProgressWebSocket, pauseWriting, resumeWriting } from '@/api/writingProgress'

const props = defineProps<{
  projectId: string
  chapterNumber: number
  initialProgress?: WritingProgress | null
}>()

const emit = defineEmits<{
  (e: 'adjust'): void
  (e: 'supplement'): void
  (e: 'stop'): void
  (e: 'view'): void
  (e: 'complete', progress: WritingProgress): void
}>()

const progress = ref<WritingProgress | null>(props.initialProgress || null)
const isPausing = ref(false)
let ws: WebSocket | null = null

// 连接 WebSocket
onMounted(() => {
  if (props.projectId && props.chapterNumber) {
    ws = connectProgressWebSocket(
      props.projectId,
      props.chapterNumber,
      (newProgress) => {
        progress.value = newProgress
        if (newProgress.status === 'completed') {
          emit('complete', newProgress)
        }
      },
      (error) => {
        console.error('进度 WebSocket 错误:', error)
      }
    )
  }
})

// 断开连接
onUnmounted(() => {
  if (ws) {
    ws.close()
    ws = null
  }
})

// 计算属性
const statusClass = computed(() => {
  if (!progress.value) return 'pending'
  return progress.value.status
})

const statusText = computed(() => {
  if (!progress.value) return '等待中'
  switch (progress.value.status) {
    case 'pending': return '等待中'
    case 'running': return '写作中'
    case 'paused': return '已暂停'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    default: return '未知'
  }
})

// 方法
function isStageActive(stage: any): boolean {
  if (!progress.value) return false
  return progress.value.current_stage === stage.stage && stage.status === 'running'
}

function formatElapsedTime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.floor(seconds)}秒`
  }
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}分${secs}秒`
}

async function handlePause() {
  isPausing.value = true
  try {
    await pauseWriting(props.projectId, props.chapterNumber)
  } catch (e) {
    console.error('暂停失败:', e)
  } finally {
    isPausing.value = false
  }
}

async function handleResume() {
  try {
    await resumeWriting(props.projectId, props.chapterNumber)
  } catch (e) {
    console.error('恢复失败:', e)
  }
}
</script>

<style scoped>
.writing-progress-board {
  background: var(--md-surface-container-low, #f5f5f5);
  border-radius: 12px;
  padding: 16px;
  max-width: 800px;
  margin: 0 auto;
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--md-outline-variant, #e0e0e0);
}

.chapter-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chapter-badge {
  background: var(--md-primary-container, #e3f2fd);
  color: var(--md-primary, #1976d2);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.pending { background: #eee; color: #666; }
.status-badge.running { background: #e3f2fd; color: #1976d2; }
.status-badge.paused { background: #fff3e0; color: #f57c00; }
.status-badge.completed { background: #e8f5e9; color: #388e3c; }
.status-badge.failed { background: #ffebee; color: #d32f2f; }

.elapsed-time {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

/* 阶段流转图 */
.stage-flow {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 0;
}

.stage-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
  position: relative;
}

.stage-node.completed .stage-icon {
  background: #e8f5e9;
}

.stage-node.running .stage-icon {
  background: #e3f2fd;
  animation: pulse 1.5s ease-in-out infinite;
}

.stage-node.failed .stage-icon {
  background: #ffebee;
}

.stage-node.paused .stage-icon {
  background: #fff3e0;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.stage-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  background: #f5f5f5;
  border: 2px solid transparent;
  transition: all 0.3s;
}

.stage-node.active .stage-icon {
  border-color: var(--md-primary, #1976d2);
  box-shadow: 0 0 8px rgba(25, 118, 210, 0.3);
}

.stage-content {
  text-align: center;
  margin-top: 8px;
}

.stage-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--md-on-surface, #333);
}

.stage-message {
  font-size: 10px;
  color: var(--md-on-surface-variant, #666);
  margin-top: 2px;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-progress-bar {
  width: 60px;
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  margin-top: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--md-primary, #1976d2);
  transition: width 0.3s;
}

/* 实时预览 */
.live-preview {
  margin-top: 16px;
  padding: 12px;
  background: white;
  border-radius: 8px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
}

.preview-header {
  margin-bottom: 8px;
}

.preview-label {
  font-size: 12px;
  color: var(--md-primary, #1976d2);
  font-weight: 500;
}

.preview-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--md-on-surface, #333);
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-family: inherit;
}

/* 干预面板 */
.intervention-panel {
  margin-top: 16px;
  padding: 12px;
  background: var(--md-surface-container-high, #fff8e1);
  border-radius: 8px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
}

.intervention-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--md-on-surface, #333);
  display: block;
  margin-bottom: 8px;
}

.intervention-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-intervene {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-intervene:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-pause { background: #fff3e0; color: #f57c00; }
.btn-pause:hover:not(:disabled) { background: #ffe0b2; }

.btn-adjust { background: #e3f2fd; color: #1976d2; }
.btn-adjust:hover { background: #bbdefb; }

.btn-supplement { background: #f3e5f5; color: #7b1fa2; }
.btn-supplement:hover { background: #e1bee7; }

.btn-stop { background: #ffebee; color: #d32f2f; }
.btn-stop:hover { background: #ffcdd2; }

/* 暂停/完成提示 */
.paused-notice,
.completed-notice {
  margin-top: 16px;
  padding: 16px;
  text-align: center;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.paused-notice {
  background: #fff3e0;
  color: #f57c00;
}

.completed-notice {
  background: #e8f5e9;
  color: #388e3c;
}

.btn-resume,
.btn-view {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  background: var(--md-primary, #1976d2);
  color: white;
}

.btn-resume:hover,
.btn-view:hover {
  opacity: 0.9;
}
</style>
