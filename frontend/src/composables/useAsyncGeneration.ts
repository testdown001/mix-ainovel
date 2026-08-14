/**
 * 异步章节生成 composable
 *
 * 整合 Task API + WebSocket，提供统一的异步章节生成接口。
 * - 优先使用 WebSocket 接收实时进度
 * - WebSocket 不可用时自动降级为轮询
 * - 兼容现有的 SSE 流式生成模式
 */
import { ref, computed } from 'vue'
import { TaskAPI, type TaskStatus } from '@/api/task'
import { useWebSocket, type TaskProgressEvent } from '@/composables/useWebSocket'
import type { AdvancedGenerateFlowConfig } from '@/api/novel'

export type GenerationMode = 'stream' | 'async'

export interface AsyncGenerationState {
  taskId: string | null
  progress: number
  stage: string
  message: string
  status: TaskStatus['status'] | null
  /**
   * 非空表示进度通道已降级（实时推送不可用 → 每 2 秒轮询）。
   * 降级本身不影响生成，但会影响进度的实时性，用户有权知道自己在看哪一种。
   */
  degradedReason?: string
}

export function useAsyncGeneration() {
  const { status: wsStatus, onTaskProgress, connect } = useWebSocket()

  const state = ref<AsyncGenerationState>({
    taskId: null,
    progress: 0,
    stage: '',
    message: '',
    status: null,
  })

  const isRunning = computed(
    () =>
      state.value.status === 'pending' ||
      state.value.status === 'queued' ||
      state.value.status === 'running' ||
      state.value.status === 'retrying',
  )

  const isCompleted = computed(() => state.value.status === 'completed')
  const isFailed = computed(() => state.value.status === 'failed')

  // 清理函数
  let cleanupWS: (() => void) | null = null

  /**
   * 提交异步生成任务
   */
  async function submitGeneration(
    projectId: string,
    chapterNumber: number,
    config?: Partial<AdvancedGenerateFlowConfig> & {
      preset?: string
      use_agent_system?: boolean
      rag_mode?: string
      writing_notes?: string
    },
    onProgress?: (s: AsyncGenerationState) => void,
  ): Promise<TaskStatus> {
    // 重置状态
    state.value = {
      taskId: null,
      progress: 0,
      stage: '提交任务...',
      message: '',
      status: 'pending',
    }

    // 提交任务
    const resp = await TaskAPI.submitChapterGenerate(projectId, chapterNumber, config)
    state.value.taskId = resp.task_id
    state.value.message = resp.message

    onProgress?.(state.value)

    // 确保 WebSocket 连接
    if (wsStatus.value !== 'connected') {
      connect()
    }

    // 尝试通过 WebSocket 接收进度
    if (wsStatus.value === 'connected') {
      return waitViaWebSocket(resp.task_id, onProgress)
    }

    // 降级为轮询
    return waitViaPolling(resp.task_id, onProgress, '实时进度推送未连接，已改为轮询获取进度')
  }

  /**
   * 提交批量生成任务
   */
  async function submitBatchGeneration(
    projectId: string,
    chapterNumbers: number[],
    config?: Partial<AdvancedGenerateFlowConfig> & {
      preset?: string
      use_agent_system?: boolean
      rag_mode?: string
    },
    onProgress?: (s: AsyncGenerationState) => void,
  ): Promise<TaskStatus> {
    state.value = {
      taskId: null,
      progress: 0,
      stage: '提交批量任务...',
      message: '',
      status: 'pending',
    }

    const resp = await TaskAPI.submitBatchGenerate(projectId, chapterNumbers, config)
    state.value.taskId = resp.task_id

    onProgress?.(state.value)

    if (wsStatus.value === 'connected') {
      return waitViaWebSocket(resp.task_id, onProgress)
    }

    return waitViaPolling(resp.task_id, onProgress, '实时进度推送未连接，已改为轮询获取进度')
  }

  /**
   * 通过 WebSocket 等待任务完成
   */
  function waitViaWebSocket(
    taskId: string,
    onProgress?: (s: AsyncGenerationState) => void,
  ): Promise<TaskStatus> {
    return new Promise((resolve, reject) => {
      let unsubscribe: (() => void) | null = null
      let checkInterval: ReturnType<typeof setInterval> | null = null

      // 超时保护
      const timeout = setTimeout(() => {
        cleanup()
        reject(new Error('任务超时（10分钟）'))
      }, 600000)

      const cleanup = () => {
        clearTimeout(timeout)
        if (checkInterval) {
          clearInterval(checkInterval)
          checkInterval = null
        }
        unsubscribe?.()
        unsubscribe = null
        cleanupWS = null
      }

      // 监听 WebSocket 事件
      unsubscribe = onTaskProgress(taskId, (event: TaskProgressEvent) => {
        state.value.progress = event.progress
        state.value.stage = event.stage
        state.value.message = event.message

        if (event.event_type === 'task_completed') {
          state.value.status = 'completed'
          state.value.progress = 100
          onProgress?.(state.value)
          cleanup()

          // 获取最终结果
          TaskAPI.getTaskStatus(taskId).then(resolve).catch(reject)
        } else if (event.event_type === 'task_failed') {
          state.value.status = 'failed'
          onProgress?.(state.value)
          cleanup()
          reject(new Error(event.message || '任务失败'))
        } else {
          // 进度更新
          if (event.event_type === 'task_started') {
            state.value.status = 'running'
          }
          onProgress?.(state.value)
        }
      })
      cleanupWS = cleanup

      // 如果 WebSocket 断开，降级到轮询
      checkInterval = setInterval(() => {
        if (wsStatus.value !== 'connected') {
          cleanup()
          waitViaPolling(taskId, onProgress, '实时进度推送已断开，已改为轮询获取进度')
            .then(resolve)
            .catch(reject)
        }
      }, 5000)
    })
  }

  /**
   * 通过轮询等待任务完成（降级方案）
   */
  async function waitViaPolling(
    taskId: string,
    onProgress?: (s: AsyncGenerationState) => void,
    degradedReason?: string,
  ): Promise<TaskStatus> {
    if (degradedReason) {
      state.value.degradedReason = degradedReason
    }

    return TaskAPI.pollUntilDone(
      taskId,
      (taskStatus) => {
        state.value.progress = taskStatus.progress
        state.value.stage = taskStatus.stage
        state.value.message = taskStatus.message
        state.value.status = taskStatus.status
        onProgress?.(state.value)
      },
      2000,
      600000,
    )
  }

  /**
   * 取消当前任务
   */
  async function cancelGeneration(): Promise<void> {
    if (state.value.taskId) {
      await TaskAPI.cancelTask(state.value.taskId)
      state.value.status = 'cancelled'
      cleanupWS?.()
      cleanupWS = null
    }
  }

  /**
   * 重置状态
   */
  function reset(): void {
    state.value = {
      taskId: null,
      progress: 0,
      stage: '',
      message: '',
      status: null,
    }
    cleanupWS?.()
    cleanupWS = null
  }

  return {
    state,
    isRunning,
    isCompleted,
    isFailed,
    submitGeneration,
    submitBatchGeneration,
    cancelGeneration,
    reset,
  }
}
