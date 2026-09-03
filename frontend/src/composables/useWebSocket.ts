/**
 * WebSocket 服务
 *
 * 连接 Go API Gateway 的 WebSocket Hub，接收实时任务进度推送。
 * 支持自动重连、心跳检测、房间订阅。
 */
import { ref, readonly } from 'vue'
import { useAuthStore } from '@/stores/auth'

export type WSStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

export interface TaskProgressEvent {
  task_id: string
  event_type: 'task_created' | 'task_started' | 'progress' | 'task_completed' | 'task_failed' | 'task_retrying'
  progress: number
  stage: string
  message: string
  user_id: number
  project_id: string
  timestamp: number
  checkpoint?: {
    kind?: string
    last_chapter?: number
    completed_chapters?: number[]
    failed_chapters?: number[]
    processed?: number
    total?: number
    parallel_workers?: number
    estimated_remaining_seconds?: number
  }
}

export type ProgressCallback = (event: TaskProgressEvent) => void

// 单例状态
const ws = ref<WebSocket | null>(null)
const status = ref<WSStatus>('disconnected')
const reconnectAttempts = ref(0)
const maxReconnectAttempts = 10
const baseReconnectDelay = 1000 // 1s，指数退避
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

// 事件监听
const progressListeners = new Map<string, Set<ProgressCallback>>() // taskId -> callbacks
const globalListeners = new Set<ProgressCallback>()

/**
 * 获取 WebSocket URL
 */
function getWSUrl(): string {
  const authStore = useAuthStore()
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const token = authStore.token || ''
  return `${protocol}//${host}/ws?token=${token}`
}

/**
 * 连接 WebSocket
 */
function connect(): void {
  if (status.value === 'connected' || status.value === 'connecting') {
    return
  }

  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }

  status.value = 'connecting'

  try {
    const socket = new WebSocket(getWSUrl())

    socket.onopen = () => {
      status.value = 'connected'
      reconnectAttempts.value = 0
      startHeartbeat()
      console.log('[WS] Connected')
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch {
        // 忽略非 JSON 消息（如 pong）
      }
    }

    socket.onclose = (event) => {
      status.value = 'disconnected'
      stopHeartbeat()
      ws.value = null

      if (!event.wasClean && reconnectAttempts.value < maxReconnectAttempts) {
        scheduleReconnect()
      }
    }

    socket.onerror = () => {
      // onclose 会在 onerror 后触发，重连逻辑在 onclose 中处理
    }

    ws.value = socket
  } catch {
    status.value = 'disconnected'
    scheduleReconnect()
  }
}

/**
 * 断开连接
 */
function disconnect(): void {
  stopHeartbeat()
  clearReconnectTimer()
  reconnectAttempts.value = 0

  if (ws.value) {
    ws.value.close(1000, 'user disconnect')
    ws.value = null
  }

  status.value = 'disconnected'
}

/**
 * 处理收到的消息
 */
function handleMessage(data: any): void {
  // 心跳响应
  if (data.type === 'pong') {
    return
  }

  // 任务进度事件
  if (data.task_id && data.event_type) {
    const event = data as TaskProgressEvent
    dispatchEvent(event)
  }
}

/**
 * 分发事件到监听器
 */
function dispatchEvent(event: TaskProgressEvent): void {
  // 通知全局监听器
  globalListeners.forEach((cb) => {
    try {
      cb(event)
    } catch (e) {
      console.error('[WS] Global listener error:', e)
    }
  })

  // 通知特定任务的监听器
  const taskListeners = progressListeners.get(event.task_id)
  if (taskListeners) {
    taskListeners.forEach((cb) => {
      try {
        cb(event)
      } catch (e) {
        console.error('[WS] Task listener error:', e)
      }
    })
  }
}

/**
 * 监听特定任务的进度
 */
function onTaskProgress(taskId: string, callback: ProgressCallback): () => void {
  if (!progressListeners.has(taskId)) {
    progressListeners.set(taskId, new Set())
  }
  progressListeners.get(taskId)!.add(callback)

  // 返回取消函数
  return () => {
    const listeners = progressListeners.get(taskId)
    if (listeners) {
      listeners.delete(callback)
      if (listeners.size === 0) {
        progressListeners.delete(taskId)
      }
    }
  }
}

/**
 * 监听所有任务进度
 */
function onAllProgress(callback: ProgressCallback): () => void {
  globalListeners.add(callback)
  return () => globalListeners.delete(callback)
}

/**
 * 加入房间（订阅特定项目的事件）
 */
function joinRoom(roomId: string): void {
  send({ type: 'join', room: roomId })
}

/**
 * 离开房间
 */
function leaveRoom(roomId: string): void {
  send({ type: 'leave', room: roomId })
}

/**
 * 发送消息
 */
function send(data: any): void {
  if (ws.value?.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify(data))
  }
}

/**
 * 心跳
 */
function startHeartbeat(): void {
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    send({ type: 'ping' })
  }, 30000) // 30s
}

function stopHeartbeat(): void {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

/**
 * 自动重连（指数退避）
 */
function scheduleReconnect(): void {
  clearReconnectTimer()

  const delay = Math.min(
    baseReconnectDelay * Math.pow(2, reconnectAttempts.value),
    30000 // 最大 30s
  )

  status.value = 'reconnecting'
  reconnectAttempts.value++

  console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.value})`)

  reconnectTimer = setTimeout(() => {
    connect()
  }, delay)
}

function clearReconnectTimer(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

/**
 * 导出 composable
 */
export function useWebSocket() {
  return {
    status: readonly(status),
    connect,
    disconnect,
    onTaskProgress,
    onAllProgress,
    joinRoom,
    leaveRoom,
    send,
  }
}
