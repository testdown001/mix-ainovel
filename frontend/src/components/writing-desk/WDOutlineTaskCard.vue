<!-- AIMETA P=章纲与正文两阶段任务卡|R=后台任务摘要_双阶段逐章状态_停止重试|NR=不发起轮询|E=component:WDOutlineTaskCard|X=ui|A=两阶段任务进度|D=vue,headlessui|S=dom|RD=./README.ai -->
<template>
  <section class="outline-task-card" :data-status="task.status" aria-live="polite">
    <div class="task-card-head">
      <span class="task-mark" :class="{ spinning: isActive }">
        <svg v-if="isActive" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 12a8 8 0 1 1-2.35-5.65" />
          <path d="M20 5v7h-7" />
        </svg>
        <svg
          v-else-if="task.status === 'completed'"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.2"
        >
          <path d="m6 12.5 3.7 3.7L18 8" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 8v5m0 3h.01" />
          <circle cx="12" cy="12" r="9" />
        </svg>
      </span>
      <span class="task-title-copy">
        <strong>{{ title }}</strong>
        <small>{{ task.message }}</small>
      </span>
      <button type="button" class="detail-link" @click="detailsOpen = true">详情</button>
    </div>

    <div class="task-numbers">
      <strong v-if="task.generate_chapters"
        >正文 {{ bodyCompletedCount }} / {{ task.total_chapters }} 章</strong
      >
      <strong v-else>章纲 {{ completedCount }} / {{ task.total_chapters }} 章</strong>
      <span v-if="retryCount" class="failed-copy">{{ retryCount }} 章待重试</span>
      <span v-else>{{ progressText }}</span>
    </div>
    <div
      class="task-progress"
      role="progressbar"
      :aria-valuenow="taskPercent"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <span :style="{ width: taskPercent + '%' }"></span>
    </div>
    <div class="task-card-foot">
      <span>{{ currentRange || stageLabel }}</span>
      <button v-if="isActive" type="button" @click="emit('cancel')">停止后续批次</button>
      <button v-else-if="retryCount" type="button" @click="emit('retry')">重试失败章节</button>
      <button v-else type="button" @click="emit('dismiss')">知道了</button>
    </div>
  </section>

  <Teleport to="body">
    <TransitionRoot as="template" :show="detailsOpen">
      <Dialog as="div" class="relative z-[90]" @close="detailsOpen = false">
        <TransitionChild
          as="template"
          enter="ease-out duration-200"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-150"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/70 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 z-10 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-200"
              enter-from="opacity-0 translate-y-3 scale-[.98]"
              enter-to="opacity-100 translate-y-0 scale-100"
              leave="ease-in duration-150"
              leave-from="opacity-100 translate-y-0 scale-100"
              leave-to="opacity-0 translate-y-3 scale-[.98]"
            >
              <DialogPanel class="task-dialog">
                <div class="dialog-head">
                  <div>
                    <p>{{ task.generate_chapters ? 'OUTLINE → MANUSCRIPT' : 'BATCH OUTLINE' }}</p>
                    <DialogTitle as="h3">
                      {{ task.generate_chapters ? '章纲与正文生成进度' : '批量章纲生成进度' }}
                    </DialogTitle>
                    <span
                      >第{{ firstChapter }}～{{ lastChapter }}章 · 共
                      {{ task.total_chapters }} 章</span
                    >
                  </div>
                  <button type="button" aria-label="关闭" @click="detailsOpen = false">×</button>
                </div>

                <div class="dialog-summary">
                  <div class="summary-number">
                    <strong>{{ completedCount }}</strong
                    ><span>章纲完成</span>
                  </div>
                  <div class="summary-number">
                    <strong>{{ task.generate_chapters ? bodyCompletedCount : pendingCount }}</strong
                    ><span>{{ task.generate_chapters ? '正文完成' : '等待中' }}</span>
                  </div>
                  <div class="summary-number is-failed">
                    <strong>{{ retryCount }}</strong
                    ><span>失败</span>
                  </div>
                  <div class="summary-stage">
                    <span>{{ stageLabel }}</span
                    ><strong>{{ progressText }}</strong>
                  </div>
                </div>

                <div class="dialog-progress">
                  <span :style="{ width: taskPercent + '%' }"></span>
                </div>
                <p class="dialog-message">{{ task.message }}</p>

                <div class="chapter-status-list">
                  <div
                    v-for="number in task.chapter_numbers"
                    :key="number"
                    class="chapter-status-row"
                    :data-state="chapterState(number)"
                  >
                    <span class="state-icon">
                      <svg
                        v-if="chapterState(number) === 'completed'"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.2"
                      >
                        <path d="m6 12.5 3.7 3.7L18 8" />
                      </svg>
                      <svg
                        v-else-if="chapterState(number) === 'running'"
                        class="spin"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M20 12a8 8 0 1 1-2.35-5.65" />
                        <path d="M20 5v7h-7" />
                      </svg>
                      <span v-else-if="chapterState(number) === 'failed'">!</span>
                      <span v-else>{{ String(number).padStart(2, '0') }}</span>
                    </span>
                    <span class="chapter-label">第 {{ number }} 章</span>
                    <span v-if="task.generate_chapters" class="phase-statuses">
                      <em :data-state="outlineState(number)"
                        >章纲 {{ outlineStateLabel(number) }}</em
                      >
                      <em :data-state="bodyState(number)">正文 {{ bodyStateLabel(number) }}</em>
                    </span>
                    <strong v-else>{{ chapterStateLabel(number) }}</strong>
                  </div>
                </div>

                <div v-if="task.error_message" class="task-error">
                  最近一次错误：{{ task.error_message }}
                </div>
                <div class="dialog-actions">
                  <button type="button" class="secondary" @click="detailsOpen = false">
                    收起到后台
                  </button>
                  <button v-if="isActive" type="button" class="danger" @click="emit('cancel')">
                    停止后续批次
                  </button>
                  <button
                    v-else-if="retryCount"
                    type="button"
                    class="primary"
                    @click="emit('retry')"
                  >
                    重试失败章节
                  </button>
                  <button v-else type="button" class="primary" @click="finishDetails">完成</button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'
import type { OutlineGenerationTask } from '@/api/novel'

const props = defineProps<{ task: OutlineGenerationTask }>()
const emit = defineEmits<{ cancel: []; retry: []; dismiss: [] }>()
const detailsOpen = ref(false)

const activeStatuses = new Set(['queued', 'running', 'cancelling'])
const completedSet = computed(() => new Set(props.task.completed_numbers || []))
const failedSet = computed(() => new Set(props.task.failed_numbers || []))
const bodyCompletedSet = computed(() => new Set(props.task.body_completed_numbers || []))
const bodyFailedSet = computed(() => new Set(props.task.body_failed_numbers || []))
const retrySet = computed(() => new Set([...failedSet.value, ...bodyFailedSet.value]))
const isActive = computed(() => activeStatuses.has(props.task.status))
const completedCount = computed(() => props.task.completed_numbers?.length || 0)
const bodyCompletedCount = computed(() => props.task.body_completed_numbers?.length || 0)
const retryCount = computed(() => retrySet.value.size)
const pendingCount = computed(() =>
  Math.max(
    0,
    props.task.total_chapters -
      (props.task.generate_chapters ? bodyCompletedCount.value : completedCount.value) -
      retryCount.value,
  ),
)
const taskPercent = computed(() => Math.max(0, Math.min(100, props.task.progress_percent || 0)))
const firstChapter = computed(() => props.task.chapter_numbers[0] ?? props.task.start_chapter)
const lastChapter = computed(() => {
  const numbers = props.task.chapter_numbers
  return numbers[numbers.length - 1] ?? props.task.start_chapter
})

const title = computed(() => {
  if (props.task.status === 'completed')
    return props.task.generate_chapters ? '章纲与正文生成完成' : '章纲生成完成'
  if (props.task.status === 'partial') return '部分章节需要重试'
  if (props.task.status === 'failed')
    return props.task.generate_chapters ? '两阶段生成失败' : '章纲生成失败'
  if (props.task.status === 'cancelled')
    return props.task.generate_chapters ? '两阶段任务已停止' : '章纲生成已停止'
  if (props.task.status === 'cancelling') return '正在停止任务'
  if (props.task.stage === 'body_generating' || props.task.stage === 'body_saving') {
    return '正在生成章节正文'
  }
  return '正在生成后续章纲'
})

const stageLabel = computed(
  () =>
    ({
      queued: '等待开始',
      preparing: '准备故事上下文',
      generating: 'AI 正在生成章纲',
      saving: '校验并保存结果',
      body_generating: 'AI 正在撰写正文',
      body_saving: '确认最佳正文版本',
      cancelling: '等待当前批次结束',
      completed: '任务已结束',
      failed: '任务执行失败',
      cancelled: '任务已停止',
    })[props.task.stage] || '处理中',
)

const currentRange = computed(() => {
  if (props.task.current_body_chapter) {
    return `正在撰写第 ${props.task.current_body_chapter} 章正文`
  }
  const start = props.task.current_batch_start
  const end = props.task.current_batch_end
  if (!start || !end) return ''
  return start === end ? `正在处理第 ${start} 章` : `正在处理第 ${start}～${end} 章`
})

const progressText = computed(() =>
  isActive.value ? `已完成 ${taskPercent.value}%` : '任务已结束',
)

function chapterState(number: number): 'completed' | 'failed' | 'running' | 'pending' {
  if (props.task.generate_chapters && bodyCompletedSet.value.has(number)) return 'completed'
  if (!props.task.generate_chapters && completedSet.value.has(number)) return 'completed'
  if (retrySet.value.has(number)) return 'failed'
  if (isActive.value && props.task.current_body_chapter === number) return 'running'
  if (
    isActive.value &&
    props.task.current_batch_start != null &&
    props.task.current_batch_end != null &&
    number >= props.task.current_batch_start &&
    number <= props.task.current_batch_end
  )
    return 'running'
  return 'pending'
}

function outlineState(number: number): 'completed' | 'failed' | 'running' | 'pending' {
  if (completedSet.value.has(number)) return 'completed'
  if (failedSet.value.has(number)) return 'failed'
  if (
    isActive.value &&
    props.task.current_batch_start != null &&
    props.task.current_batch_end != null &&
    number >= props.task.current_batch_start &&
    number <= props.task.current_batch_end
  )
    return 'running'
  return 'pending'
}

function bodyState(number: number): 'completed' | 'failed' | 'running' | 'pending' | 'blocked' {
  if (bodyCompletedSet.value.has(number)) return 'completed'
  if (bodyFailedSet.value.has(number)) return 'failed'
  if (isActive.value && props.task.current_body_chapter === number) return 'running'
  if (failedSet.value.has(number) || !completedSet.value.has(number)) return 'blocked'
  return 'pending'
}

function outlineStateLabel(number: number): string {
  return { completed: '已完成', failed: '失败', running: '生成中', pending: '等待中' }[
    outlineState(number)
  ]
}

function bodyStateLabel(number: number): string {
  return {
    completed: '已完成',
    failed: '失败',
    running: '生成中',
    pending: '待生成',
    blocked: '等待章纲',
  }[bodyState(number)]
}

function chapterStateLabel(number: number): string {
  const state = chapterState(number)
  if (state === 'completed') return '已完成'
  if (state === 'failed') return '生成失败'
  if (state === 'running') return '生成中'
  return '等待生成'
}

function finishDetails(): void {
  emit('dismiss')
  detailsOpen.value = false
}
</script>

<style scoped>
.outline-task-card {
  padding: 12px;
  border: 1px solid #393724;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(255, 229, 0, 0.07), rgba(24, 25, 21, 0.98) 52%);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
}
.outline-task-card[data-status='failed'],
.outline-task-card[data-status='partial'] {
  border-color: rgba(255, 111, 111, 0.3);
}
.task-card-head {
  display: flex;
  align-items: center;
  gap: 9px;
}
.task-mark {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(255, 229, 0, 0.28);
  border-radius: 8px;
  color: #ffe500;
  background: rgba(255, 229, 0, 0.08);
}
.task-mark svg {
  width: 15px;
  height: 15px;
}
.task-mark.spinning svg,
.spin {
  animation: task-spin 1.2s linear infinite;
}
.task-title-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}
.task-title-copy strong {
  color: #f0f0e9;
  font-size: 11px;
  line-height: 16px;
}
.task-title-copy small {
  overflow: hidden;
  margin-top: 1px;
  color: #777a72;
  font-size: 9px;
  line-height: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-link,
.task-card-foot button {
  border: 0;
  color: #d7ca1b;
  font-size: 9px;
  font-weight: 650;
  background: none;
  cursor: pointer;
}
.task-numbers {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  color: #777a72;
  font-size: 9px;
}
.task-numbers strong {
  color: #e3e3dc;
  font-size: 11px;
}
.failed-copy {
  color: #ff8181;
}
.task-progress {
  height: 4px;
  margin-top: 7px;
  overflow: hidden;
  border-radius: 99px;
  background: #2a2b26;
}
.task-progress span,
.dialog-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #b7a900, #ffe500);
  transition: width 0.35s ease;
}
.task-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
  color: #92958c;
  font-size: 9px;
}
.task-dialog {
  width: min(620px, calc(100vw - 24px));
  overflow: hidden;
  border: 1px solid #30312c;
  border-radius: 22px;
  color: #e9e9e2;
  background: #151613;
  box-shadow: 0 30px 100px rgba(0, 0, 0, 0.62);
}
.dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 24px 26px 18px;
  border-bottom: 1px solid #282924;
}
.dialog-head p {
  margin: 0 0 5px;
  color: #8c8614;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.16em;
}
.dialog-head h3 {
  margin: 0;
  color: #f5f5ee;
  font-size: 21px;
}
.dialog-head span {
  display: block;
  margin-top: 6px;
  color: #7f827a;
  font-size: 12px;
}
.dialog-head button {
  border: 0;
  color: #898c84;
  font-size: 28px;
  line-height: 1;
  background: none;
}
.dialog-summary {
  display: grid;
  grid-template-columns: repeat(3, 82px) 1fr;
  gap: 10px;
  padding: 18px 26px 12px;
}
.summary-number,
.summary-stage {
  display: flex;
  min-height: 60px;
  flex-direction: column;
  justify-content: center;
  padding: 10px 12px;
  border: 1px solid #292a25;
  border-radius: 11px;
  background: #1b1c19;
}
.summary-number strong {
  color: #ffe500;
  font-size: 19px;
}
.summary-number span,
.summary-stage span {
  color: #73766f;
  font-size: 9px;
}
.summary-number.is-failed strong {
  color: #ff8181;
}
.summary-stage strong {
  margin-top: 4px;
  color: #dadbd3;
  font-size: 11px;
}
.dialog-progress {
  height: 5px;
  margin: 0 26px;
  overflow: hidden;
  border-radius: 99px;
  background: #292a25;
}
.dialog-message {
  margin: 9px 26px 13px;
  color: #9a9d94;
  font-size: 11px;
}
.chapter-status-list {
  display: grid;
  max-height: 320px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
  overflow-y: auto;
  padding: 0 26px 20px;
  scrollbar-width: thin;
  scrollbar-color: #3a3b35 transparent;
}
.chapter-status-row {
  display: grid;
  grid-template-columns: 28px minmax(70px, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid #292a25;
  border-radius: 10px;
  background: #191a17;
}
.state-icon {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid #353630;
  border-radius: 50%;
  color: #777a72;
  font-size: 9px;
}
.state-icon svg {
  width: 14px;
  height: 14px;
}
.chapter-status-row[data-state='completed'] .state-icon,
.chapter-status-row[data-state='completed'] strong {
  color: #36d885;
}
.chapter-status-row[data-state='running'] .state-icon,
.chapter-status-row[data-state='running'] strong {
  color: #ffe500;
}
.chapter-status-row[data-state='failed'] .state-icon,
.chapter-status-row[data-state='failed'] strong {
  color: #ff8181;
}
.chapter-label {
  color: #d7d8d0;
  font-size: 11px;
}
.chapter-status-row strong {
  color: #73766f;
  font-size: 9px;
}
.phase-statuses {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}
.phase-statuses em {
  color: #73766f;
  font-size: 8px;
  font-style: normal;
  white-space: nowrap;
}
.phase-statuses em[data-state='completed'] {
  color: #36d885;
}
.phase-statuses em[data-state='running'] {
  color: #ffe500;
}
.phase-statuses em[data-state='failed'] {
  color: #ff8181;
}
.task-error {
  margin: 0 26px 18px;
  padding: 10px 12px;
  border-radius: 9px;
  color: #e99696;
  font-size: 10px;
  background: rgba(150, 35, 35, 0.12);
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 15px 26px 20px;
  border-top: 1px solid #282924;
}
.dialog-actions button {
  padding: 9px 15px;
  border: 1px solid #343630;
  border-radius: 9px;
  color: #b5b7ae;
  font-size: 11px;
  font-weight: 650;
  background: #1c1d1a;
}
.dialog-actions .primary {
  border-color: #ffe500;
  color: #111;
  background: #ffe500;
}
.dialog-actions .danger {
  border-color: rgba(255, 111, 111, 0.35);
  color: #ff8e8e;
  background: rgba(120, 28, 28, 0.12);
}
@keyframes task-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 620px) {
  .dialog-summary {
    grid-template-columns: repeat(3, 1fr);
  }
  .summary-stage {
    grid-column: 1 / -1;
  }
  .chapter-status-list {
    grid-template-columns: 1fr;
  }
}
</style>
