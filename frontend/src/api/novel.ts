// AIMETA P=小说API客户端_小说和章节接口|R=小说CRUD_章节管理_生成|NR=不含UI逻辑|E=api:novel|X=internal|A=novelApi对象|D=axios|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// API 配置
// 开发环境使用相对路径，由 Vite 代理转发到后端（vite.config.ts 中配置）
// 生产环境同样使用相对路径，由反向代理（nginx 等）转发
export const API_BASE_URL = ''
export const API_PREFIX = '/api'

// 统一的请求处理函数
const request = async (url: string, options: RequestInit = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  // 如果 body 是 FormData，删除 Content-Type header，让浏览器自动设置（包含 boundary）
  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  }

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    // Token 失效或未授权
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (!response.ok) {
    let detail = ''
    const contentType = (response.headers.get('content-type') || '').toLowerCase()

    if (contentType.includes('application/json')) {
      const errorData = await response.json().catch(() => null as any)
      if (typeof errorData?.detail === 'string' && errorData.detail.trim()) {
        detail = errorData.detail.trim()
      } else if (typeof errorData?.message === 'string' && errorData.message.trim()) {
        detail = errorData.message.trim()
      } else if (typeof errorData?.error?.message === 'string' && errorData.error.message.trim()) {
        detail = errorData.error.message.trim()
      } else if (errorData) {
        detail = JSON.stringify(errorData)
      }
    } else {
      detail = (await response.text().catch(() => '')).trim()
    }

    if (detail) {
      const clipped = detail.length > 600 ? `${detail.slice(0, 600)}...` : detail
      throw new Error(`请求失败(${response.status}): ${clipped}`)
    }
    throw new Error(`请求失败，状态码: ${response.status}`)
  }

  return response.json()
}

// 类型定义
export interface NovelProject {
  id: string
  title: string
  initial_prompt: string
  blueprint?: Blueprint
  chapters: Chapter[]
  conversation_history: ConversationMessage[]
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}

export interface Blueprint {
  title?: string
  target_audience?: string
  genre?: string
  style?: string
  tone?: string
  one_sentence_summary?: string
  full_synopsis?: string
  world_setting?: any
  characters?: Character[]
  relationships?: any[]
  chapter_outline?: ChapterOutline[]
}

export interface Character {
  name: string
  description: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
}

export interface ChapterBeat {
  type: 'setup' | 'provoke' | 'twist' | 'payoff' | 'hook'
  content: string
  emotion: string
}

export interface ChapterPrediction {
  key_points: string[]
  cool_points: string[]
  foreshadowing_hooks: string[]
  foreshadowing_targets: string[]
  limitations: string[]
  beats?: ChapterBeat[]
}

export interface ChapterOutline {
  chapter_number: number
  title: string
  summary: string
  metadata?: { prediction?: ChapterPrediction } | null
}

export interface RegenerateOutlinesResponse {
  updated_chapters: number[]
  total_target: number
  chapter_outline: ChapterOutline[]
}

export interface ChapterVersion {
  content: string
  style?: string
  metadata?: ChapterVersionMetadata
}

export interface ChapterVersionMetadata {
  version_id?: number
  version_label?: string
  ai_review?: {
    is_best?: boolean
    scores?: Record<string, number>
    evaluation?: string | null
    flaws?: string[] | null
    suggestions?: string | null
  }
  [key: string]: any
}

export interface Chapter {
  chapter_number: number
  title: string
  summary: string
  content: string | null
  versions: string[] | null  // versions是字符串数组，不是对象数组
  version_metadata?: ChapterVersionMetadata[] | null
  recommended_version_index?: number | null
  evaluation: string | null
  generation_status: 'not_generated' | 'generating' | 'evaluating' | 'selecting' | 'failed' | 'evaluation_failed' | 'waiting_for_confirm' | 'successful'
  word_count?: number  // 字数统计
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ConverseResponse {
  ai_message: string
  ui_control: UIControl
  conversation_state: any
  is_complete: boolean
  ready_for_blueprint?: boolean  // 新增：表示准备生成蓝图
}

export interface BlueprintGenerationResponse {
  blueprint: Blueprint
  ai_message: string
}

export interface UIControl {
  type: 'single_choice' | 'text_input'
  options?: Array<{ id: string; label: string }>
  placeholder?: string
}

export interface ChapterGenerationResponse {
  versions: ChapterVersion[] // Renamed from chapter_versions for consistency
  evaluation: string | null
  ai_message: string
  chapter_number: number
}

export interface AdvancedGenerateFlowConfig {
  preset?: 'basic' | 'enhanced' | 'ultimate' | 'platinum' | 'custom'
  versions?: number
  enable_preview?: boolean
  enable_optimizer?: boolean
  enable_consistency?: boolean
  enable_enrichment?: boolean
  async_finalize?: boolean
  enable_rag?: boolean
  rag_mode?: 'simple' | 'two_stage'
}

export interface AdvancedGenerateRequest {
  project_id: string
  chapter_number: number
  writing_notes?: string
  flow_config?: AdvancedGenerateFlowConfig
}

export interface AdvancedGenerateVariant {
  index: number
  version_id: number
  content: string
  metadata?: ChapterVersionMetadata
}

export interface AdvancedGenerateResponse {
  project_id: string
  chapter_number: number
  preset: string
  best_version_index: number
  variants: AdvancedGenerateVariant[]
  review_summaries?: Record<string, any>
  debug_metadata?: Record<string, any> | null
}

export interface DeleteNovelsResponse {
  status: string
  message: string
}

// 内容型Section（对应后端NovelSectionType枚举）
export type NovelSectionType = 'overview' | 'world_setting' | 'characters' | 'relationships' | 'chapter_outline' | 'chapters'

// 分析型Section（不属于NovelSectionType，使用独立的analytics API）
export type AnalysisSectionType = 'emotion_curve' | 'foreshadowing'

// 所有Section的联合类型
export type AllSectionType = NovelSectionType | AnalysisSectionType

export interface NovelSectionResponse {
  section: NovelSectionType
  data: Record<string, any>
}

// API 函数
const NOVELS_BASE = `${API_BASE_URL}${API_PREFIX}/novels`
const WRITER_PREFIX = '/api/writer'
const WRITER_BASE = `${API_BASE_URL}${WRITER_PREFIX}/novels`

export class NovelAPI {
  static async createNovel(title: string, initialPrompt: string): Promise<NovelProject> {
    return request(NOVELS_BASE, {
      method: 'POST',
      body: JSON.stringify({ title, initial_prompt: initialPrompt })
    })
  }

  static async importNovel(file: File): Promise<{ id: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return request(`${NOVELS_BASE}/import`, {
      method: 'POST',
      body: formData,
      headers: {
        // 让 browser 自动设置 Content-Type 为 multipart/form-data，不手动设置
      }
    })
  }

  static async getNovel(projectId: string): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}`)
  }

  static async getChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return request(`${NOVELS_BASE}/${projectId}/chapters/${chapterNumber}`)
  }

  static async getSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return request(`${NOVELS_BASE}/${projectId}/sections/${section}`)
  }

  static async converseConcept(
    projectId: string,
    userInput: any,
    conversationState: any = {}
  ): Promise<ConverseResponse> {
    const formattedUserInput = userInput || { id: null, value: null }
    return request(`${NOVELS_BASE}/${projectId}/concept/converse`, {
      method: 'POST',
      body: JSON.stringify({
        user_input: formattedUserInput,
        conversation_state: conversationState
      })
    })
  }

  static async generateBlueprint(projectId: string): Promise<BlueprintGenerationResponse> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 2_100_000) // 35 分钟超时（thinking 模式下蓝图生成可能需要 20-30 分钟）
    try {
      return await request(`${NOVELS_BASE}/${projectId}/blueprint/generate`, {
        method: 'POST',
        signal: controller.signal,
      })
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error('蓝图生成超时（已等待35分钟），请重试。如果持续超时请联系管理员。')
      }
      throw err
    } finally {
      clearTimeout(timeoutId)
    }
  }

  static async saveBlueprint(projectId: string, blueprint: Blueprint): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/save`, {
      method: 'POST',
      body: JSON.stringify(blueprint)
    })
  }

  static async generateChapter(projectId: string, chapterNumber: number, writingNotes?: string): Promise<NovelProject> {
    const payload: AdvancedGenerateRequest = {
      project_id: projectId,
      chapter_number: chapterNumber,
      ...(writingNotes ? { writing_notes: writingNotes } : {}),
      flow_config: { preset: 'enhanced' }
    }

    await request(`${API_BASE_URL}${WRITER_PREFIX}/advanced/generate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })

    return this.getNovel(projectId)
  }

  static async evaluateChapter(projectId: string, chapterNumber: number): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ chapter_number: chapterNumber })
    })
  }

  static async selectChapterVersion(
    projectId: string,
    chapterNumber: number,
    versionIndex: number
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/select`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        version_index: versionIndex
      })
    })
  }

  static async getAllNovels(): Promise<NovelProjectSummary[]> {
    return request(NOVELS_BASE)
  }

  static async deleteNovels(projectIds: string[]): Promise<DeleteNovelsResponse> {
    return request(NOVELS_BASE, {
      method: 'DELETE',
      body: JSON.stringify(projectIds)
    })
  }

  static async updateChapterOutline(
    projectId: string,
    chapterOutline: ChapterOutline
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/update-outline`, {
      method: 'POST',
      body: JSON.stringify(chapterOutline)
    })
  }

  static async deleteChapter(
    projectId: string,
    chapterNumbers: number[]
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/delete`, {
      method: 'POST',
      body: JSON.stringify({ chapter_numbers: chapterNumbers })
    })
  }

  static async generateChapterOutline(
    projectId: string,
    startChapter: number,
    numChapters: number
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/outline`, {
      method: 'POST',
      body: JSON.stringify({
        start_chapter: startChapter,
        num_chapters: numChapters
      })
    })
  }

  static async regenerateOutlines(
    projectId: string,
    chapterNumbers?: number[]
  ): Promise<RegenerateOutlinesResponse> {
    return request(`${WRITER_BASE}/${projectId}/chapters/regenerate-outlines`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_numbers: chapterNumbers || null
      })
    })
  }

  static async updateBlueprint(projectId: string, data: Record<string, any>): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  }

  static async rebuildRag(projectId: string): Promise<{ indexed_chapters: number }> {
    return request(`${WRITER_BASE}/${projectId}/rag/rebuild`, { method: 'POST' })
  }

  static async generatePrediction(projectId: string, chapterNumber: number): Promise<ChapterPrediction> {
    return request(`${WRITER_BASE}/${projectId}/chapters/${chapterNumber}/prediction`, {
      method: 'POST'
    })
  }

  static async editChapterContent(
    projectId: string,
    chapterNumber: number,
    content: string
  ): Promise<Chapter> {
    return request(`${WRITER_BASE}/${projectId}/chapters/edit-fast`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        content: content
      })
    })
  }
}


// 优化相关类型定义
export interface EmotionBeat {
  primary_emotion: string
  intensity: number
  curve: {
    start: number
    peak: number
    end: number
  }
  turning_point: string
}

export interface OptimizeRequest {
  project_id: string
  chapter_number: number
  dimension: 'dialogue' | 'environment' | 'psychology' | 'rhythm'
  additional_notes?: string
}

export interface OptimizeResponse {
  optimized_content: string
  optimization_notes: string
  dimension: string
}

// 优化API
const OPTIMIZER_BASE = `${API_BASE_URL}${API_PREFIX}/optimizer`

export class OptimizerAPI {
  /**
   * 对章节内容进行分层优化
   */
  static async optimizeChapter(optimizeReq: OptimizeRequest): Promise<OptimizeResponse> {
    return request(`${OPTIMIZER_BASE}/optimize`, {
      method: 'POST',
      body: JSON.stringify(optimizeReq)
    })
  }

  /**
   * 应用优化后的内容到章节
   */
  static async applyOptimization(
    projectId: string,
    chapterNumber: number,
    optimizedContent: string
  ): Promise<{ status: string; message: string }> {
    return request(`${OPTIMIZER_BASE}/apply-optimization`, {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        chapter_number: chapterNumber,
        optimized_content: optimizedContent
      })
    })
  }
}
