// AIMETA P=小说API客户端_小说和章节接口|R=小说CRUD_章节管理_生成|NR=不含UI逻辑|E=api:novel|X=internal|A=novelApi对象|D=axios|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { StreamInterruptedError } from '@/utils/streamInterruption'

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

  if (response.status === 204 || response.status === 205) {
    return undefined as any
  }

  const contentType = (response.headers.get('content-type') || '').toLowerCase()
  if (contentType.includes('application/json')) {
    return response.json()
  }

  const text = await response.text().catch(() => '')
  return (text ? text : undefined) as any
}

// 类型定义
export interface NovelProject {
  id: string
  title: string
  initial_prompt: string
  is_completed?: boolean
  reference_novel_ids?: number[]
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
  is_completed?: boolean
}

export interface BlueprintVolume {
  name?: string
  start_chapter?: number
  end_chapter?: number
  arc_goal?: string
  climax_hint?: string
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
  volumes?: BlueprintVolume[]
  golden_finger?: Record<string, any> | null
  foreshadowings?: BlueprintForeshadowing[]
  review_report?: BlueprintReviewReport | null
}

export interface BlueprintForeshadowing {
  name?: string
  description?: string
  planted_chapter?: number
  target_chapter?: number | null
  tier?: string
  type?: string
  reveal_method?: string | null
  reveal_impact?: string | null
}

export interface ReviewIssue {
  dimension?: string
  severity?: string
  target?: string
  problem?: string
  fix_hint?: string
}

export interface BlueprintReviewReport {
  total_score?: number
  dimension_scores?: Record<string, number>
  verdict?: string
  issues?: ReviewIssue[]
  strengths?: string[]
  revised?: boolean
}

// ── 故事立项书（结构化前提产物）+ 压力推演报告 ──

export interface DossierProtagonist {
  name?: string
  identity?: string
  desire?: string
  flaw?: string
  predicament?: string
  charm_point?: string
}

export interface DossierGoldenFinger {
  name?: string
  source?: string
  mechanism?: string
  limitations?: string
  growth_curve?: string
}

export interface DossierAnticipation {
  ten_chapters?: string
  fifty_chapters?: string
  long_term?: string
}

export interface ConceptDossier {
  core_selling_line?: string
  genre?: string
  audience?: string
  platform_mode?: string
  protagonist?: DossierProtagonist
  core_conflict?: string
  conflict_engine?: string
  golden_finger?: DossierGoldenFinger | null
  anticipation?: DossierAnticipation
  coolpoint_chain?: string[]
  title_candidates?: string[]
  notes?: string
}

export interface ToxicPoint {
  issue?: string
  severity?: string
  reason?: string
  fix_suggestion?: string
}

export interface StressReport {
  conflict_sustainability?: {
    at_50?: string
    at_100?: string
    at_300?: string
    verdict?: string
    analysis?: string
  }
  golden_finger_collapse?: {
    stall_chapter?: number
    stall_reason?: string
    verdict?: string
    analysis?: string
  }
  toxic_points?: ToxicPoint[]
  overall_verdict?: string
  summary?: string
}

export type BlueprintDepth = 'fast' | 'deep'

export interface DossierResponse {
  status: 'ready' | 'absent'
  dossier: ConceptDossier | null
  stress_report: StressReport | null
  stress_available: boolean
  deep_available: boolean
  /** 深度打磨积分单价；审稿门关闭时为 0 */
  deep_credit_price: number
  generated_at?: string | null
}

export interface Character {
  name: string
  description: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
  power_system_id?: number
  current_power_level_id?: number
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

export interface ChapterPlanning {
  chapter_function?: string
  hook_type?: string
  coolpoint?: string
  foreshadowing_ops?: { op: string; name: string }[]
  must_not_include?: string[]
}

export interface ChapterOutline {
  chapter_number: number
  title: string
  summary: string
  metadata?: { prediction?: ChapterPrediction; planning?: ChapterPlanning } | null
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

export interface ReferenceSearchResponse {
  reference_context: string
  search_completed: boolean
  skipped: boolean
  message?: string
  searched_novels: string[]
}

export interface MemoryCard {
  genre?: string
  core_selling_point?: string
  target_audience?: string
  cool_point_patterns?: string[]
  pacing_traits?: string
  world_type?: string
  main_conflict_pattern?: string
  narrative_pov?: string
  foreshadowing_techniques?: string[]
  suspense_techniques?: string[]
  dialogue_style?: string
  scene_transition_style?: string
  emotion_control_pattern?: string
  commercial_data?: Record<string, string>
  takeaways?: string[]
  risks?: string[]
}

export interface ReferenceNovelSummary {
  id: number
  title: string
  genre?: string
  author?: string
  status: string
  created_at: string
  updated_at: string
}

/** 桥段：参考小说在某类局面下的处理手法（情境→铺垫→转折→兑现）。 */
export interface ReferenceBeat {
  name?: string
  situation?: string
  tags?: string[]
  setup?: string
  turn?: string
  payoff?: string
  pitfalls?: string
}

export interface BeatLibrary {
  beats?: ReferenceBeat[]
  structure?: {
    volume_rhythm?: string
    conflict_escalation?: string
    hook_pattern?: string
  }
}

/** 写法基准：可执行的写法约束（约束「怎么写」，不约束写什么）。 */
export interface StyleGuide {
  narrative_pov?: string
  sentence_rhythm?: string
  dialogue_style?: string
  description_density?: string
  paragraphing?: string
  emotion_expression?: string
  signature_devices?: string[]
  forbidden?: string[]
}

export interface ReferenceNovelDetail extends ReferenceNovelSummary {
  outline_content?: string
  style_samples_content?: string
  memory_card?: MemoryCard
  beat_library?: BeatLibrary
  style_guide?: StyleGuide
  source_url?: string
  error_message?: string
}

export interface ReferenceNovelCreatePayload {
  title: string
  author?: string
  genre?: string
}

export interface ReferenceNovelUpdatePayload {
  outline_content?: string
  style_samples_content?: string
  memory_card?: MemoryCard
  genre?: string
  author?: string
  source_url?: string
  status?: string
  error_message?: string
}

export interface ReferenceNovelBindPayload {
  reference_novel_ids: number[]
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

export interface MusePersona {
  key: string
  label: string
  blurb: string
}

export interface MusePersonasResponse {
  personas: MusePersona[]
  tier: 'free' | 'creator' | 'flagship'
  features: {
    muse_persona: boolean
    muse_search: boolean
    muse_divergence: boolean
  }
}

export interface DivergeSeed {
  id: number
  title: string
  logline: string
  hook: string
  world: string
  tone: string
  twist: string
  novelty?: number
  marketability?: number
  coherence?: number
  score?: number
  verdict?: string
}

export interface DivergeResponse {
  seeds: DivergeSeed[]
  tier: string
}

export interface ChapterGenerationResponse {
  versions: ChapterVersion[] // Renamed from chapter_versions for consistency
  evaluation: string | null
  ai_message: string
  chapter_number: number
}

export interface AdvancedGenerateFlowConfig {
  selected_skills?: Array<{
    skill_id: string
    capability_name?: string
    params?: Record<string, unknown>
  }>
  preset?: 'fast' | 'standard' | 'premium' | 'basic' | 'enhanced' | 'ultimate' | 'platinum' | 'literary' | 'custom'
  model_code?: string
  enable_polish?: boolean
  versions?: number
  enable_preview?: boolean
  enable_optimizer?: boolean
  enable_consistency?: boolean
  enable_enrichment?: boolean
  async_finalize?: boolean
  enable_rag?: boolean
  rag_mode?: 'simple' | 'two_stage'
  enable_scene_by_scene?: boolean
  enable_prose_sculpting?: boolean
  enable_golden_paragraph?: boolean
  enable_reference_prose?: boolean
  enable_voice_samples?: boolean
  enable_narrative_variety?: boolean
  use_slim_prompt?: boolean
  enable_fast_path?: boolean
  disable_guardrail_rewrite?: boolean
  skip_history_summary_backfill?: boolean
  use_local_anti_hallucination?: boolean
  use_agent?: boolean
  use_agentic_loop?: boolean
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

export interface AdvancedGenerateStreamStagePayload {
  stage?: string
  message?: string
  chapter_number?: number
  [key: string]: any
}

export interface AdvancedGenerateStreamTextDeltaPayload {
  delta?: string
  stage?: string
  chapter_number?: number
  [key: string]: any
}

export interface AdvancedGenerateStreamCallbacks {
  onEvent?: (event: string, payload: any) => void
  onStage?: (payload: AdvancedGenerateStreamStagePayload) => void
  onTextDelta?: (delta: string, payload: AdvancedGenerateStreamTextDeltaPayload) => void
  onError?: (error: Error, payload?: any) => void
}

export interface BatchGenerateChapterResult {
  chapter_number: number
  status: 'success' | 'failed'
  error?: string
}

export interface BatchGenerateResponse {
  project_id: string
  total: number
  completed: number
  failed: number
  results: BatchGenerateChapterResult[]
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
const REFERENCE_LIBRARY_BASE = `${API_BASE_URL}${API_PREFIX}/reference-novels`
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
    conversationState: any = {},
    options: {
      referenceNovels?: string[]
      referenceContext?: string
      exclusions?: string
      musePersona?: string
      disableSpark?: boolean
      disableMuseSearch?: boolean
    } = {}
  ): Promise<ConverseResponse> {
    const formattedUserInput = userInput || { id: null, value: null }
    const payload: Record<string, any> = {
      user_input: formattedUserInput,
      conversation_state: conversationState
    }
    if (options.musePersona && options.musePersona !== 'default') {
      payload.muse_persona = options.musePersona
    }
    if (options.disableSpark) payload.disable_spark = true
    if (options.disableMuseSearch) payload.disable_muse_search = true
    const normalizedReferenceNovels = (options.referenceNovels || [])
      .map((name) => (name || '').trim())
      .filter(Boolean)
      .slice(0, 3)
    if (normalizedReferenceNovels.length > 0) {
      payload.reference_novels = normalizedReferenceNovels
    }
    if (options.referenceContext && options.referenceContext.trim()) {
      payload.reference_context = options.referenceContext.trim()
    }
    if (options.exclusions && options.exclusions.trim()) {
      payload.exclusions = options.exclusions.trim()
    }
    return request(`${NOVELS_BASE}/${projectId}/concept/converse`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  /** 获取缪斯人格清单 + 当前用户订阅档位与特性可用性。 */
  static async listMusePersonas(): Promise<MusePersonasResponse> {
    return request(`${NOVELS_BASE}/concept/personas`)
  }

  /** 读取故事立项书（对话完成后后台已蒸馏，未就绪时本请求会同步补齐，首次可能 30-90 秒）。 */
  static async getConceptDossier(projectId: string): Promise<DossierResponse> {
    return request(`${NOVELS_BASE}/${projectId}/concept/dossier`)
  }

  /** 分块编辑立项书（只提交改动的顶层键）。 */
  static async patchConceptDossier(
    projectId: string,
    partial: Record<string, any>
  ): Promise<{ status: string; dossier: ConceptDossier }> {
    return request(`${NOVELS_BASE}/${projectId}/concept/dossier`, {
      method: 'PATCH',
      body: JSON.stringify({ dossier: partial })
    })
  }

  /** 采纳压力推演的修复建议：一轮 LLM 修订写回立项书。 */
  static async applyDossierFixes(
    projectId: string
  ): Promise<{ status: string; dossier: ConceptDossier; stress_report: StressReport }> {
    return request(`${NOVELS_BASE}/${projectId}/concept/dossier/apply-fixes`, {
      method: 'POST'
    })
  }

  /** N 路发散（旗舰档）：一次生成 N 个迥异种子并评分收敛到 Top。 */
  static async divergeConcepts(
    projectId: string,
    seedTopic: string,
    options: { exclusions?: string; n?: number; keep?: number } = {}
  ): Promise<DivergeResponse> {
    return request(`${NOVELS_BASE}/${projectId}/concept/diverge`, {
      method: 'POST',
      body: JSON.stringify({
        seed_topic: seedTopic,
        exclusions: options.exclusions || undefined,
        n: options.n ?? 5,
        keep: options.keep ?? 3
      })
    })
  }

  static async searchReferenceNovels(
    projectId: string,
    novelNames: string[]
  ): Promise<ReferenceSearchResponse> {
    const normalized = (novelNames || [])
      .map((name) => (name || '').trim())
      .filter(Boolean)
      .slice(0, 3)
    return request(`${NOVELS_BASE}/${projectId}/reference-search`, {
      method: 'POST',
      body: JSON.stringify({ novel_names: normalized })
    })
  }

  static async listReferenceNovelLibrary(search?: string): Promise<ReferenceNovelSummary[]> {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    return request(`${REFERENCE_LIBRARY_BASE}${query}`)
  }

  static async createReferenceNovel(payload: ReferenceNovelCreatePayload): Promise<ReferenceNovelSummary> {
    return request(REFERENCE_LIBRARY_BASE, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static async getReferenceNovel(novelId: number): Promise<ReferenceNovelDetail> {
    return request(`${REFERENCE_LIBRARY_BASE}/${novelId}`)
  }

  static async updateReferenceNovel(novelId: number, payload: ReferenceNovelUpdatePayload): Promise<ReferenceNovelDetail> {
    return request(`${REFERENCE_LIBRARY_BASE}/${novelId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  }

  static async deleteReferenceNovel(novelId: number): Promise<void> {
    await request(`${REFERENCE_LIBRARY_BASE}/${novelId}`, {
      method: 'DELETE'
    })
  }

  static async analyzeReferenceNovel(novelId: number): Promise<ReferenceNovelDetail> {
    return request(`${REFERENCE_LIBRARY_BASE}/${novelId}/analyze`, {
      method: 'POST'
    })
  }

  static async listProjectReferenceNovels(projectId: string): Promise<ReferenceNovelSummary[]> {
    return request(`${NOVELS_BASE}/${projectId}/reference-novels`)
  }

  static async bindProjectReferenceNovels(projectId: string, payload: ReferenceNovelBindPayload): Promise<{ status: string; bound_ids: number[] }> {
    return request(`${NOVELS_BASE}/${projectId}/reference-novels/bind`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static async generateBlueprint(
    projectId: string,
    depth: BlueprintDepth = 'deep'
  ): Promise<BlueprintGenerationResponse> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 2_100_000) // 35 分钟超时（thinking 模式下蓝图生成可能需要 20-30 分钟）
    try {
      return await request(`${NOVELS_BASE}/${projectId}/blueprint/generate`, {
        method: 'POST',
        body: JSON.stringify({ depth }),
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

  static async generateChapter(
    projectId: string,
    chapterNumber: number,
    writingNotes?: string,
    preset: AdvancedGenerateFlowConfig['preset'] = 'fast',
    flowConfigOverrides?: Partial<AdvancedGenerateFlowConfig>
  ): Promise<NovelProject> {
    const payload: AdvancedGenerateRequest = {
      project_id: projectId,
      chapter_number: chapterNumber,
      ...(writingNotes ? { writing_notes: writingNotes } : {}),
      flow_config: { preset, ...flowConfigOverrides }
    }

    await request(`${API_BASE_URL}${WRITER_PREFIX}/advanced/generate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })

    return this.getNovel(projectId)
  }

  /**
   * 生成章节并返回原始 AdvancedGenerateResponse（含 best_version_index），供连续生成使用
   */
  static async generateChapterRaw(
    projectId: string,
    chapterNumber: number,
    writingNotes?: string,
    preset: AdvancedGenerateFlowConfig['preset'] = 'fast',
    flowConfigOverrides?: Partial<AdvancedGenerateFlowConfig>
  ): Promise<AdvancedGenerateResponse> {
    const payload: AdvancedGenerateRequest = {
      project_id: projectId,
      chapter_number: chapterNumber,
      ...(writingNotes ? { writing_notes: writingNotes } : {}),
      flow_config: { preset, ...flowConfigOverrides }
    }

    return request(`${API_BASE_URL}${WRITER_PREFIX}/advanced/generate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static async generateChapterStream(
    projectId: string,
    chapterNumber: number,
    writingNotes?: string,
    preset: AdvancedGenerateFlowConfig['preset'] = 'fast',
    callbacks: AdvancedGenerateStreamCallbacks = {},
    flowConfigOverrides?: Partial<AdvancedGenerateFlowConfig>
  ): Promise<AdvancedGenerateResponse> {
    const payload: AdvancedGenerateRequest = {
      project_id: projectId,
      chapter_number: chapterNumber,
      ...(writingNotes ? { writing_notes: writingNotes } : {}),
      flow_config: { preset, ...flowConfigOverrides }
    }

    const authStore = useAuthStore()
    const headers = new Headers({
      'Content-Type': 'application/json'
    })
    if (authStore.isAuthenticated && authStore.token) {
      headers.set('Authorization', `Bearer ${authStore.token}`)
    }

    const response = await fetch(`${API_BASE_URL}${WRITER_PREFIX}/advanced/generate/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    })

    if (response.status === 401) {
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

    if (!response.body) {
      throw new Error('流式响应为空')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let completedPayload: AdvancedGenerateResponse | null = null

    const handleEventBlock = (rawBlock: string) => {
      const block = rawBlock.trim()
      if (!block || block.startsWith(':')) {
        return
      }

      let eventName = 'message'
      const dataLines: string[] = []
      for (const line of block.split('\n')) {
        if (!line) continue
        if (line.startsWith(':')) continue
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim() || 'message'
          continue
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart())
        }
      }

      const rawData = dataLines.join('\n')
      let payloadData: any = {}
      if (rawData) {
        try {
          payloadData = JSON.parse(rawData)
        } catch {
          payloadData = { message: rawData }
        }
      }

      callbacks.onEvent?.(eventName, payloadData)

      if (eventName === 'stage') {
        callbacks.onStage?.(payloadData as AdvancedGenerateStreamStagePayload)
        return
      }

      if (eventName === 'text_delta') {
        const textDelta = typeof payloadData?.delta === 'string' ? payloadData.delta : ''
        if (textDelta) {
          callbacks.onTextDelta?.(textDelta, payloadData as AdvancedGenerateStreamTextDeltaPayload)
        }
        return
      }

      if (eventName === 'completed') {
        completedPayload = payloadData as AdvancedGenerateResponse
        return
      }

      if (eventName === 'error') {
        const detail = typeof payloadData?.detail === 'string' ? payloadData.detail : '生成失败'
        const error = new Error(detail)
        callbacks.onError?.(error, payloadData)
        throw error
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n')

        let separatorIndex = buffer.indexOf('\n\n')
        while (separatorIndex !== -1) {
          const block = buffer.slice(0, separatorIndex)
          buffer = buffer.slice(separatorIndex + 2)
          handleEventBlock(block)
          separatorIndex = buffer.indexOf('\n\n')
        }
      }

      const tail = decoder.decode()
      if (tail) {
        buffer += tail
      }
      buffer = buffer.replace(/\r\n/g, '\n')
      if (buffer.trim()) {
        handleEventBlock(buffer)
      }
    } finally {
      await reader.cancel().catch(() => undefined)
    }

    if (!completedPayload) {
      // 流断在中途（网络抖动/代理超时/服务端被重启）。这不是业务失败：服务端很可能
      // 还在写这一章（实测断线后生成会跑完并落库）。抛专用错误类型让调用方去跟后端
      // 对账，而不是直接报红说「生成失败」。
      throw new StreamInterruptedError()
    }
    return completedPayload
  }

  static async batchGenerateChapters(
    projectId: string,
    chapterNumbers: number[],
    writingNotes?: string,
    preset: AdvancedGenerateFlowConfig['preset'] = 'fast'
  ): Promise<BatchGenerateResponse> {
    return request(`${API_BASE_URL}${WRITER_PREFIX}/advanced/batch-generate`, {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        chapter_numbers: chapterNumbers,
        ...(writingNotes ? { writing_notes: writingNotes } : {}),
        flow_config: { preset }
      })
    })
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
    numChapters: number,
    estimatedTotalChapters?: number,
    userPrompt?: string
  ): Promise<NovelProject> {
    const body: Record<string, any> = {
      start_chapter: startChapter,
      num_chapters: numChapters
    }
    if (estimatedTotalChapters && estimatedTotalChapters > 0) {
      body.estimated_total_chapters = estimatedTotalChapters
    }
    if (userPrompt && userPrompt.trim()) {
      body.user_prompt = userPrompt.trim()
    }
    return request(`${WRITER_BASE}/${projectId}/chapters/outline`, {
      method: 'POST',
      body: JSON.stringify(body)
    })
  }

  static async regenerateOutlines(
    projectId: string,
    chapterNumbers?: number[],
    totalChapters?: number
  ): Promise<RegenerateOutlinesResponse> {
    const body: Record<string, any> = {}
    if (chapterNumbers) body.chapter_numbers = chapterNumbers
    if (totalChapters) body.total_chapters = totalChapters
    return request(`${WRITER_BASE}/${projectId}/chapters/regenerate-outlines`, {
      method: 'POST',
      body: JSON.stringify(body)
    })
  }

  static async updateBlueprint(projectId: string, data: Record<string, any>): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  }

  static async setCompleted(projectId: string, isCompleted: boolean): Promise<{ status: string; is_completed: boolean }> {
    return request(`${NOVELS_BASE}/${projectId}/completed`, {
      method: 'PATCH',
      body: JSON.stringify({ is_completed: isCompleted })
    })
  }

  static async generateForeshadowings(projectId: string): Promise<{ status: string; message: string; total: number }> {
    return request(`${NOVELS_BASE}/${projectId}/foreshadowings/generate`, { method: 'POST' })
  }

  static async rebuildRag(projectId: string, forceFull: boolean = false): Promise<{ indexed_chapters: number; skipped_chapters: number; removed_chapters: number }> {
    return request(`${WRITER_BASE}/${projectId}/rag/rebuild?force_full=${forceFull}`, { method: 'POST' })
  }

  static async previewContextPlan(
    projectId: string,
    chapterNumber: number,
    params: { writing_notes?: string; preset?: string; selected_skills?: any[] }
  ): Promise<any> {
    return request(`${WRITER_BASE}/${projectId}/chapters/${chapterNumber}/preview-plan`, {
      method: 'POST',
      body: JSON.stringify(params)
    })
  }

  static async rebuildVolumeSummaries(projectId: string, force: boolean = false): Promise<{ updated: number; skipped: number; total_volumes: number; mode: string }> {
    return request(`${WRITER_BASE}/${projectId}/volumes/rebuild-summaries`, {
      method: 'POST',
      body: JSON.stringify({ force })
    })
  }

  static async getVolumeSummaries(projectId: string): Promise<Array<{ volume_number: number; title: string; chapter_start: number; chapter_end: number; chapter_count: number; summary: string; updated_at: string | null }>> {
    return request(`${WRITER_BASE}/${projectId}/volumes/summaries`)
  }

  static async getBookSummary(projectId: string): Promise<{ summary: string | null }> {
    return request(`${WRITER_BASE}/${projectId}/book-summary`)
  }

  static async rebuildBookSummary(projectId: string, force: boolean = false): Promise<{ summary: string | null; mode: string }> {
    return request(`${WRITER_BASE}/${projectId}/book-summary/rebuild`, {
      method: 'POST',
      body: JSON.stringify({ force })
    })
  }

  static async generatePrediction(projectId: string, chapterNumber: number, exclusions?: string): Promise<ChapterPrediction> {
    return request(`${WRITER_BASE}/${projectId}/chapters/${chapterNumber}/prediction`, {
      method: 'POST',
      body: JSON.stringify({ exclusions: exclusions || '' })
    })
  }

  static async batchGeneratePredictions(projectId: string): Promise<{ queued: number; chapter_numbers: number[]; message: string }> {
    return request(`${WRITER_BASE}/${projectId}/chapters/batch-prediction`, {
      method: 'POST'
    })
  }

  static async getPredictionProgress(projectId: string): Promise<{ running: boolean; total: number; completed: number; failed: number }> {
    return request(`${WRITER_BASE}/${projectId}/chapters/prediction-progress`)
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

  /**
   * 一键生成角色DNA档案
   */
  static async generateCharacterDNA(
    projectId: string,
    characterNames?: string[],
    overwrite: boolean = false
  ): Promise<{ status: string; message: string; updated_characters: string[] }> {
    return request(`${NOVELS_BASE}/${projectId}/characters/generate-dna`, {
      method: 'POST',
      body: JSON.stringify({
        character_names: characterNames || null,
        overwrite
      })
    })
  }

  static async syncCharactersFromChapters(
    projectId: string
  ): Promise<{ status: string; message: string; new_characters: any[] }> {
    return request(`${NOVELS_BASE}/${projectId}/characters/sync-from-chapters`, {
      method: 'POST'
    })
  }

  static async syncRelationshipsFromChapters(
    projectId: string
  ): Promise<{ status: string; message: string; new_relationships: any[] }> {
    return request(`${NOVELS_BASE}/${projectId}/relationships/sync-from-chapters`, {
      method: 'POST'
    })
  }

  // ---- 场景管理 API ----

  static async getChapterScenes(projectId: string, chapterNumber: number): Promise<{ chapter_number: number; scenes: any[] }> {
    return request(`${NOVELS_BASE}/${projectId}/outlines/${chapterNumber}/scenes`)
  }

  static async updateChapterScenes(projectId: string, chapterNumber: number, scenes: any[]): Promise<any> {
    return request(`${NOVELS_BASE}/${projectId}/outlines/${chapterNumber}/scenes`, {
      method: 'PUT',
      body: JSON.stringify({ scenes })
    })
  }

  static async generateChapterScenes(projectId: string, chapterNumber: number): Promise<any> {
    return request(`${NOVELS_BASE}/${projectId}/outlines/${chapterNumber}/scenes/generate`, {
      method: 'POST'
    })
  }
}

// ---- 概念库 / 设定百科 API ----

export interface Concept {
  id: number
  entity_type: string
  canonical_name: string
  description: string | null
  properties: Record<string, any>
  aliases: string[]
  source: string
  first_chapter: number | null
  created_at: string | null
}

export class ConceptAPI {
  static async list(projectId: string, entityType?: string): Promise<Concept[]> {
    const params = entityType ? `?entity_type=${entityType}` : ''
    return request(`${NOVELS_BASE}/${projectId}/concepts${params}`)
  }

  static async create(projectId: string, data: {
    entity_type: string
    canonical_name: string
    description?: string
    properties?: Record<string, any>
    aliases?: string[]
  }): Promise<{ id: number; message: string }> {
    return request(`${NOVELS_BASE}/${projectId}/concepts`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  static async update(projectId: string, conceptId: number, data: {
    entity_type?: string
    canonical_name?: string
    description?: string
    properties?: Record<string, any>
    aliases?: string[]
  }): Promise<{ message: string }> {
    return request(`${NOVELS_BASE}/${projectId}/concepts/${conceptId}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    })
  }

  static async delete(projectId: string, conceptId: number): Promise<{ message: string }> {
    return request(`${NOVELS_BASE}/${projectId}/concepts/${conceptId}`, {
      method: 'DELETE'
    })
  }

  static async generate(projectId: string): Promise<{ status: string; message: string; count: number }> {
    return request(`${NOVELS_BASE}/${projectId}/concepts/generate`, {
      method: 'POST'
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

// ========== 任务档案 API ==========

export interface WritingArchive {
  id: number
  project_id: string
  chapter_number: number
  user_command: string | null
  writing_notes: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  version_count: number | null
  gatekeeper_score: number | null
  user_rating: number | null
  created_at: string | null
}

export interface WritingArchiveDetail extends WritingArchive {
  stages: Record<string, any> | null
  logs: Array<{
    timestamp: string
    level: string
    message: string
  }> | null
  final_version_id: number | null
  final_version_content: string | null
}

export interface ArchiveStats {
  total_tasks: number
  completed_tasks: number
  avg_gatekeeper_score: number | null
  avg_duration_seconds: number | null
  total_versions_generated: number
}

export const archiveApi = {
  // 获取项目所有档案列表
  async getProjectArchives(projectId: string, limit = 50, offset = 0): Promise<WritingArchive[]> {
    return request(`${API_PREFIX}/writer/novels/${projectId}/archives?limit=${limit}&offset=${offset}`)
  },

  // 获取单个档案详情
  async getArchiveDetail(projectId: string, archiveId: number): Promise<WritingArchiveDetail> {
    return request(`${API_PREFIX}/writer/novels/${projectId}/archives/${archiveId}`)
  },

  // 获取章节最新档案
  async getLatestArchive(projectId: string, chapterNumber: number): Promise<WritingArchive> {
    return request(`${API_PREFIX}/writer/novels/${projectId}/archives/chapter/${chapterNumber}/latest`)
  },

  // 获取项目写作统计
  async getProjectStats(projectId: string): Promise<ArchiveStats> {
    return request(`${API_PREFIX}/writer/novels/${projectId}/archives/stats/summary`)
  },

  // 为档案评分
  async rateArchive(projectId: string, archiveId: number, rating: number): Promise<{ id: number; user_rating: number }> {
    return request(`${API_PREFIX}/writer/novels/${projectId}/archives/${archiveId}/rate`, {
      method: 'POST',
      body: JSON.stringify(rating)
    })
  }
}

// ---- 诊断 API ----
export const diagnosticApi = {
  // 诊断单章生成质量和性能
  async diagnoseChapter(projectId: string, chapterNumber: number) {
    return request(`${API_PREFIX}/writer/novels/${projectId}/chapters/${chapterNumber}/diagnose`)
  },

  // 诊断整本书生成质量和性能
  async diagnoseProject(projectId: string) {
    return request(`${API_PREFIX}/writer/novels/${projectId}/diagnose`)
  },
}
