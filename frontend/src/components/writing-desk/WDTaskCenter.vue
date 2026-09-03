<template>
  <section class="task-center" :class="{ expanded: open }" aria-label="创作任务中心">
    <button class="task-center__toggle" type="button" @click="open = !open">
      <span class="task-center__pulse" :class="{ active: activeCount > 0 }"></span>
      <span class="task-center__title">创作任务</span>
      <span v-if="activeCount" class="task-center__active">{{ activeCount }} 个进行中</span>
      <span v-else class="task-center__quiet">任务状态已同步</span>
      <span class="task-center__chevron">{{ open ? '⌄' : '⌃' }}</span>
    </button>

    <div v-if="open" class="task-center__panel">
      <header>
        <div>
          <strong>本书任务</strong>
          <small>离开页面后也会继续执行</small>
        </div>
        <button type="button" class="refresh" :disabled="loading" @click="loadTasks">刷新</button>
      </header>

      <p v-if="error" class="task-center__error">{{ error }}</p>
      <div v-if="loading && !tasks.length" class="task-center__empty">正在同步任务状态…</div>
      <div v-else-if="!visibleTasks.length" class="task-center__empty">暂无近期任务</div>
      <article v-for="task in visibleTasks" :key="task.task_id" class="task-row">
        <div class="task-row__top">
          <span class="task-row__name">{{ taskName(task) }}</span>
          <span class="task-row__status" :class="`is-${task.status}`">{{ statusName(task) }}</span>
        </div>
        <div class="task-row__message">{{ task.message || '等待任务状态…' }}</div>
        <div class="task-row__bar"><i :style="{ width: `${Math.min(100, Math.max(0, task.progress || 0))}%` }"></i></div>
        <div class="task-row__meta">
          <span>{{ task.progress || 0 }}%</span>
          <span v-if="task.checkpoint?.last_chapter">已处理至第 {{ task.checkpoint.last_chapter }} 章</span>
          <button
            v-if="canRetry(task)"
            type="button"
            class="retry"
            :disabled="retrying === task.task_id"
            @click="retry(task)"
          >
            {{ retrying === task.task_id ? '提交中…' : retryLabel(task) }}
          </button>
        </div>
        <div v-if="task.checkpoint?.failed_chapters?.length" class="task-row__failed">
          失败章节：{{ task.checkpoint.failed_chapters.join('、') }}（可单独续跑）
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { TaskAPI, type TaskStatus } from '@/api/task'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ (e: 'updated'): void; (e: 'resumed', task: TaskStatus): void }>()

const authStore = useAuthStore()
const open = ref(false)
const loading = ref(false)
const error = ref('')
const tasks = ref<TaskStatus[]>([])
const retrying = ref<string | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

const visibleTasks = computed(() => tasks.value.filter((task) => task.project_id === props.projectId).slice(0, 8))
const activeCount = computed(() => visibleTasks.value.filter((task) => ['pending', 'queued', 'running', 'retrying'].includes(task.status)).length)

function taskName(task: TaskStatus) {
  if (task.type === 'chapter:batch_generate') return '批量生成章节正文'
  if (task.type === 'chapter:generate') return '生成单章正文'
  if (task.type === 'blueprint:generate') return '生成全书蓝图'
  return '创作任务'
}

function statusName(task: TaskStatus) {
  if (task.status === 'completed' && task.result?.status === 'partial') return '部分完成'
  return ({ pending: '准备中', queued: '排队中', running: '执行中', retrying: '自动重试中', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[task.status] || task.status
}

function canRetry(task: TaskStatus) {
  if (task.status === 'failed' || task.status === 'cancelled') return true
  return task.type === 'chapter:batch_generate' && task.status === 'completed' && task.result?.status === 'partial'
}

function retryLabel(task: TaskStatus) {
  return task.type === 'chapter:batch_generate' ? '仅续跑失败章节' : '重新执行'
}

async function loadTasks() {
  const userId = authStore.user?.id
  if (!userId || !props.projectId) return
  loading.value = true
  error.value = ''
  try {
    const response = await TaskAPI.getUserTasks(userId)
    tasks.value = response.tasks || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务状态同步失败'
  } finally {
    loading.value = false
  }
}

async function retry(task: TaskStatus) {
  retrying.value = task.task_id
  try {
    await TaskAPI.retryTask(task.task_id)
    await loadTasks()
    emit('resumed', task)
    emit('updated')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '续跑任务提交失败'
  } finally {
    retrying.value = null
  }
}

watch(() => props.projectId, loadTasks)
onMounted(() => {
  loadTasks()
  timer = setInterval(loadTasks, 5000)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.task-center { position: fixed; right: 22px; bottom: 22px; z-index: 40; width: min(380px, calc(100vw - 32px)); color: #e9e9e4; font-size: 13px; }
.task-center__toggle { display: flex; align-items: center; gap: 9px; width: 100%; padding: 11px 14px; border: 1px solid #34352d; border-radius: 14px; background: rgba(22, 23, 20, .96); color: inherit; box-shadow: 0 9px 30px rgba(0,0,0,.32); cursor: pointer; text-align: left; }
.task-center.expanded .task-center__toggle { border-radius: 14px 14px 0 0; border-bottom-color: #22231e; }
.task-center__pulse { width: 8px; height: 8px; border-radius: 50%; background: #62645d; }
.task-center__pulse.active { background: #d7ca00; box-shadow: 0 0 0 4px rgba(215,202,0,.13); }
.task-center__title { font-weight: 700; }
.task-center__active { color: #d7ca00; }
.task-center__quiet { color: #85877f; }
.task-center__chevron { margin-left: auto; color: #aaa; font-size: 16px; }
.task-center__panel { max-height: min(65vh, 560px); overflow: auto; padding: 14px; border: 1px solid #34352d; border-top: 0; border-radius: 0 0 14px 14px; background: rgba(18,19,17,.98); box-shadow: 0 16px 36px rgba(0,0,0,.4); }
.task-center__panel header { display:flex; align-items:center; justify-content:space-between; margin-bottom: 11px; }
.task-center__panel header strong { display:block; font-size: 15px; }
.task-center__panel header small { display:block; margin-top: 3px; color:#777970; }
.refresh, .retry { border: 1px solid #4b4c3b; border-radius: 8px; background: transparent; color: #d7ca00; padding: 5px 9px; cursor: pointer; }
.refresh:disabled, .retry:disabled { opacity: .55; cursor: wait; }
.task-center__empty { padding: 24px 0; color: #74766e; text-align: center; }
.task-center__error { padding: 8px 10px; border-radius: 8px; background: #3a1718; color: #ff9b9f; }
.task-row { padding: 11px 0; border-top: 1px solid #292a25; }
.task-row__top, .task-row__meta { display:flex; align-items:center; gap: 8px; }
.task-row__name { font-weight: 650; }
.task-row__status { margin-left:auto; color:#93958d; font-size: 12px; }
.task-row__status.is-running, .task-row__status.is-retrying { color:#d7ca00; }
.task-row__status.is-completed { color:#36d488; }
.task-row__status.is-failed { color:#ff6b72; }
.task-row__message { margin: 6px 0; color:#9b9d95; white-space: nowrap; overflow:hidden; text-overflow:ellipsis; }
.task-row__bar { height: 5px; overflow:hidden; border-radius: 5px; background:#2b2c28; }
.task-row__bar i { display:block; height:100%; border-radius:inherit; background:#d7ca00; transition: width .3s ease; }
.task-row__meta { margin-top: 6px; color:#74766e; font-size: 11px; }
.retry { margin-left:auto; padding: 3px 7px; font-size: 11px; }
.task-row__failed { margin-top: 6px; color:#e5a04c; font-size: 11px; }
@media (max-width: 640px) { .task-center { right: 12px; bottom: 12px; } }
</style>
