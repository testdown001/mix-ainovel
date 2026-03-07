// 写作进度 API
import { http } from './http'

export interface StageProgress {
  stage: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked' | 'paused'
  progress: number
  message: string
  started_at?: number
  completed_at?: number
  error?: string
  metadata: Record<string, any>
  display: {
    name: string
    icon: string
    description: string
  }
}

export interface WritingProgress {
  project_id: string
  chapter_number: number
  chapter_title: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed'
  current_stage: string | null
  stages: StageProgress[]
  started_at: number
  elapsed_seconds: number
  can_intervene: boolean
  last_output_preview: string
}

// REST API
export async function getWritingProgress(projectId: string, chapterNumber: number): Promise<WritingProgress | null> {
  try {
    const res = await http.get(`/api/writer/progress/${projectId}/${chapterNumber}`)
    return res.data
  } catch (e) {
    console.warn('获取写作进度失败:', e)
    return null
  }
}

// WebSocket 连接
export function connectProgressWebSocket(
  projectId: string,
  chapterNumber: number,
  onMessage: (progress: WritingProgress) => void,
  onError?: (error: Event) => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/writer/progress/${projectId}/${chapterNumber}`
  
  const ws = new WebSocket(wsUrl)
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.data) {
        onMessage(data.data)
      }
    } catch (e) {
      console.error('解析进度消息失败:', e)
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket 错误:', error)
    onError?.(error)
  }
  
  return ws
}

// 暂停/恢复
export async function pauseWriting(projectId: string, chapterNumber: number): Promise<boolean> {
  const res = await http.post(`/api/writer/progress/${projectId}/${chapterNumber}/pause`)
  return res.data.success
}

export async function resumeWriting(projectId: string, chapterNumber: number): Promise<boolean> {
  const res = await http.post(`/api/writer/progress/${projectId}/${chapterNumber}/resume`)
  return res.data.success
}
