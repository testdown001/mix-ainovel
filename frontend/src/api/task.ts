/**
 * Task API
 *
 * 对接 Go Task Dispatcher 的任务管理接口。
 * 支持提交异步任务、查询状态、取消任务。
 */
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import type { AdvancedGenerateFlowConfig } from './novel'

const TASK_BASE = '/tasks'

// 统一请求（复用 novel.ts 的模式，但指向 Go Gateway 的 /tasks 路径）
const taskRequest = async (url: string, options: RequestInit = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers,
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (!response.ok) {
    const contentType = (response.headers.get('content-type') || '').toLowerCase()
    let detail = ''
    if (contentType.includes('application/json')) {
      const errorData = await response.json().catch(() => null)
      detail =
        errorData?.error || errorData?.detail || errorData?.message || JSON.stringify(errorData)
    } else {
      detail = await response.text().catch(() => '')
    }
    const err = new Error(detail || `请求失败(${response.status})`) as Error & { status?: number }
    err.status = response.status
    throw err
  }

  return response.json()
}

// ============================================================
// 类型定义
// ============================================================

export interface TaskSubmitRequest {
  type: 'chapter:generate' | 'chapter:batch_generate' | 'blueprint:generate'
  project_id: string
  chapter_number?: number
  chapter_numbers?: number[]
  user_id: number
  priority?: number // 0=low, 1=default, 2=high, 3=critical
  config?: {
    preset?: string
    use_agent_system?: boolean
    rag_mode?: string
    writing_notes?: string
    [key: string]: any
  }
}

export interface TaskSubmitResponse {
  task_id: string
  status: string
  message: string
  created_at: string
}

export interface TaskStatus {
  task_id: string
  type: string
  project_id?: string
  parent_task_id?: string
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'retrying'
  progress: number // 0-100
  stage: string
  message: string
  error: string
  result: any
  checkpoint?: {
    kind?: string
    last_chapter?: number
    completed_chapters?: number[]
    failed_chapters?: number[]
    total?: number
  } | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  retry_count: number
}

export interface DispatcherStats {
  dispatcher: {
    active_tasks: number
    max_concurrency: number
    running: boolean
    queue_lengths: Array<{
      name: string
      priority: number
      length: number
    }>
  }
  workers: Array<{
    id: string
    base_url: string
    healthy: boolean
    active_jobs: number
    max_jobs: number
  }>
}

// ============================================================
// API 函数
// ============================================================

export class TaskAPI {
  /**
   * 提交章节生成任务
   */
  static async submitChapterGenerate(
    projectId: string,
    chapterNumber: number,
    config?: Partial<AdvancedGenerateFlowConfig> & {
      preset?: string
      use_agent_system?: boolean
      rag_mode?: string
      writing_notes?: string
    },
    priority: number = 1,
  ): Promise<TaskSubmitResponse> {
    const authStore = useAuthStore()
    return taskRequest(`${TASK_BASE}/submit`, {
      method: 'POST',
      body: JSON.stringify({
        type: 'chapter:generate',
        project_id: projectId,
        chapter_number: chapterNumber,
        user_id: authStore.user?.id || 0,
        priority,
        config,
      }),
    })
  }

  /**
   * 提交批量生成任务
   */
  static async submitBatchGenerate(
    projectId: string,
    chapterNumbers: number[],
    config?: Partial<AdvancedGenerateFlowConfig> & {
      preset?: string
      use_agent_system?: boolean
      rag_mode?: string
    },
    priority: number = 0,
  ): Promise<TaskSubmitResponse> {
    const authStore = useAuthStore()
    return taskRequest(`${TASK_BASE}/submit`, {
      method: 'POST',
      body: JSON.stringify({
        type: 'chapter:batch_generate',
        project_id: projectId,
        chapter_numbers: chapterNumbers,
        user_id: authStore.user?.id || 0,
        priority,
        config,
      }),
    })
  }

  /**
   * 提交蓝图生成任务
   *
   * 蓝图两段式 LLM 生成可长达 10 分钟以上，同步直连在生产会被网关/nginx 超时掐断
   * （后端实际已成功落库但前端看到失败），故生产链路走异步任务路径。
   */
  static async submitBlueprintGenerate(
    projectId: string,
    depth: 'fast' | 'deep' = 'deep',
    priority: number = 1,
  ): Promise<TaskSubmitResponse> {
    const authStore = useAuthStore()
    return taskRequest(`${TASK_BASE}/submit`, {
      method: 'POST',
      body: JSON.stringify({
        type: 'blueprint:generate',
        project_id: projectId,
        user_id: authStore.user?.id || 0,
        priority,
        config: { depth },
      }),
    })
  }

  /**
   * 查询任务状态
   */
  static async getTaskStatus(taskId: string): Promise<TaskStatus> {
    return taskRequest(`${TASK_BASE}/${taskId}/status`)
  }

  /**
   * 取消任务
   */
  static async cancelTask(
    taskId: string,
  ): Promise<{ task_id: string; status: string; message: string }> {
    return taskRequest(`${TASK_BASE}/${taskId}/cancel`, { method: 'POST' })
  }

  /** 从失败检查点创建新任务；批量任务只会提交失败章节。 */
  static async retryTask(
    taskId: string,
  ): Promise<TaskSubmitResponse> {
    return taskRequest(`${TASK_BASE}/${taskId}/retry`, { method: 'POST' })
  }

  /**
   * 获取用户任务列表
   */
  static async getUserTasks(
    userId: number,
  ): Promise<{ user_id: number; tasks: TaskStatus[]; count: number }> {
    return taskRequest(`${TASK_BASE}/user/${userId}`)
  }

  /**
   * 获取调度器统计
   */
  static async getStats(): Promise<DispatcherStats> {
    return taskRequest(`${TASK_BASE}/stats`)
  }

  /**
   * 轮询任务状态直到完成（WebSocket 不可用时的降级方案）
   */
  static async pollUntilDone(
    taskId: string,
    onProgress?: (status: TaskStatus) => void,
    intervalMs: number = 2000,
    timeoutMs: number | null = null,
  ): Promise<TaskStatus> {
    const startTime = Date.now()
    const MAX_POLL_CONSECUTIVE_ERRORS = 3
    let consecutiveErrors = 0

    return new Promise((resolve, reject) => {
      const poll = async () => {
        if (timeoutMs !== null && timeoutMs > 0 && Date.now() - startTime > timeoutMs) {
          reject(new Error('任务超时'))
          return
        }

        try {
          const status = await TaskAPI.getTaskStatus(taskId)
          consecutiveErrors = 0
          onProgress?.(status)

          if (status.status === 'completed') {
            resolve(status)
            return
          }

          if (status.status === 'failed') {
            reject(new Error(status.error || '任务执行失败'))
            return
          }

          if (status.status === 'cancelled') {
            reject(new Error('任务已取消'))
            return
          }

          // 继续轮询
          setTimeout(poll, intervalMs)
        } catch (e) {
          // 长任务轮询窗口内数百次请求，单次网络抖动不应整体判败（后端任务仍在跑，
          // 误报失败会诱导用户重新发起 → 同一任务双跑）；连续多次失败才放弃
          consecutiveErrors += 1
          if (consecutiveErrors >= MAX_POLL_CONSECUTIVE_ERRORS) {
            reject(e)
            return
          }
          setTimeout(poll, intervalMs)
        }
      }

      poll()
    })
  }
}
