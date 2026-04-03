<!-- AIMETA P=概览区_仪表盘式概览|R=统计卡片_最近章节_角色_AI分析|NR=不含编辑功能|E=component:OverviewSection|X=ui|A=概览组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <!-- Completion Status Toggle -->
    <div v-if="editable" class="flex items-center justify-between rounded-2xl border border-[#2A2A2A] bg-[#141414] px-6 py-4">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl flex items-center justify-center"
          :style="{ background: localCompleted ? 'rgba(46, 213, 115, 0.15)' : 'rgba(255, 229, 0, 0.15)' }">
          <svg v-if="localCompleted" class="w-5 h-5" style="color: #2ED573;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else class="w-5 h-5" style="color: #FFE500;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </div>
        <div>
          <div class="text-sm font-semibold text-white">小说状态</div>
          <div class="text-xs" :style="{ color: localCompleted ? '#2ED573' : '#888' }">
            {{ localCompleted ? '已完结' : '连载中' }}
          </div>
        </div>
      </div>
      <button
        @click="toggleCompleted"
        :disabled="completedToggling"
        class="relative inline-flex h-7 w-12 items-center rounded-full transition-colors duration-200 focus:outline-none"
        :style="{ background: localCompleted ? '#2ED573' : '#2A2A2A', cursor: completedToggling ? 'not-allowed' : 'pointer', border: 'none' }"
      >
        <span
          class="inline-block h-5 w-5 rounded-full transition-transform duration-200"
          :style="{ background: '#fff', transform: localCompleted ? 'translateX(22px)' : 'translateX(4px)' }"
        />
      </button>
    </div>

    <!-- Stats + AI Analysis: Two Column Layout -->
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <!-- Left Column: Stats + Recent Chapters + Characters -->
      <div class="lg:col-span-3 space-y-6">
        <!-- Stat Cards Row -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <!-- Total Words -->
          <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-5">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style="background: rgba(255, 107, 53, 0.15);">
              <svg class="w-5 h-5" style="color: #FF6B35;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div class="flex items-baseline gap-1">
              <span class="text-2xl font-bold text-white">{{ formatNumber(totalWords) }}</span>
              <span class="text-sm text-[#666]">字</span>
            </div>
            <div class="text-xs text-[#555] mt-1">总字数</div>
          </div>

          <!-- Chapters -->
          <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-5">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style="background: rgba(99, 102, 241, 0.15);">
              <svg class="w-5 h-5" style="color: #6366F1;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div class="flex items-baseline gap-1">
              <span class="text-2xl font-bold text-white">{{ completedChapters }}</span>
              <span class="text-sm text-[#666]">/{{ totalOutlines || '—' }}章</span>
            </div>
            <div class="text-xs text-[#555] mt-1">章节数</div>
          </div>

          <!-- AI Generation Rate -->
          <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-5">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style="background: rgba(46, 213, 115, 0.15);">
              <svg class="w-5 h-5" style="color: #2ED573;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div class="flex items-baseline gap-1">
              <span class="text-2xl font-bold text-white">{{ aiRate }}</span>
              <span class="text-sm text-[#666]">%</span>
            </div>
            <div class="text-xs text-[#555] mt-1">AI生成率</div>
          </div>

          <!-- Average Quality -->
          <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-5">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style="background: rgba(255, 229, 0, 0.15);">
              <svg class="w-5 h-5" style="color: #FFE500;" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            </div>
            <div class="flex items-baseline gap-1">
              <span class="text-2xl font-bold text-white">{{ avgQuality > 0 ? avgQuality : '—' }}</span>
              <span v-if="avgQuality > 0" class="text-sm text-[#666]">/100</span>
            </div>
            <div class="text-xs text-[#555] mt-1">平均质量</div>
          </div>
        </div>

        <!-- Recent Chapters -->
        <div>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-base font-semibold text-white">最近章节</h3>
            <button
              v-if="recentChapters.length > 0"
              class="text-sm transition-colors"
              style="color: #888;"
              @click="$emit('switch-section', 'chapters')"
              @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
              @mouseleave="($event.target as HTMLElement).style.color='#888'"
            >查看全部</button>
          </div>
          <div v-if="recentChapters.length > 0" class="space-y-3">
            <div
              v-for="(chapter, idx) in recentChapters"
              :key="chapter.chapter_number"
              class="rounded-xl border border-[#2A2A2A] bg-[#141414] p-4 flex items-center gap-4 hover:border-[#3A3A3A] transition-colors"
            >
              <div
                class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
                :style="{ background: chapterColors[idx % chapterColors.length].bg, color: chapterColors[idx % chapterColors.length].text }"
              >
                {{ chapter.chapter_number }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-white truncate">{{ chapter.title }}</div>
                <div class="text-xs mt-1" style="color: #666;">
                  {{ formatNumber(chapter.word_count || 0) }}字 · {{ formatRelativeDate(chapter) }}
                </div>
              </div>
              <div
                v-if="getChapterScore(chapter) !== null"
                class="px-3 py-1.5 rounded-lg text-sm font-semibold flex-shrink-0"
                :style="{ color: scoreColor(getChapterScore(chapter)!), background: scoreBackground(getChapterScore(chapter)!) }"
              >
                {{ getChapterScore(chapter) }}
              </div>
            </div>
          </div>
          <div v-else class="rounded-xl border border-dashed border-[#2A2A2A] bg-[#141414] p-10 text-center text-sm" style="color: #555;">
            暂无已生成的章节
          </div>
        </div>

        <!-- Main Characters -->
        <div>
          <h3 class="text-base font-semibold text-white mb-4">主要人物</h3>
          <div v-if="displayCharacters.length > 0" class="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div
              v-for="char in displayCharacters"
              :key="char.name"
              class="rounded-xl border border-[#2A2A2A] bg-[#141414] p-5 text-center hover:border-[#3A3A3A] transition-colors cursor-pointer"
              @click="$emit('switch-section', 'characters')"
            >
              <div
                class="w-14 h-14 mx-auto rounded-full flex items-center justify-center text-2xl mb-3"
                :style="{ background: getRoleStyle(char.identity).avatarBg }"
              >
                {{ getRoleEmoji(char.identity) }}
              </div>
              <div class="text-sm font-medium text-white mb-2 truncate">{{ char.name }}</div>
              <span
                class="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium"
                :style="{ background: getRoleStyle(char.identity).tagBg, color: getRoleStyle(char.identity).tagText }"
              >
                {{ getRoleLabel(char.identity) }}
              </span>
            </div>
          </div>
          <div v-else class="rounded-xl border border-dashed border-[#2A2A2A] bg-[#141414] p-10 text-center text-sm" style="color: #555;">
            暂无角色信息
          </div>
        </div>

        <!-- Full Synopsis (collapsible) -->
        <div v-if="data?.full_synopsis" class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-6">
          <div class="flex items-start justify-between gap-4 mb-4">
            <h3 class="text-base font-semibold text-white">完整剧情梗概</h3>
            <button
              v-if="editable"
              type="button"
              class="text-[#555] hover:text-[#FFE500] transition-colors flex-shrink-0"
              @click="emitEdit('full_synopsis', '完整剧情梗概', data?.full_synopsis)"
            >
              <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
          <p class="text-sm leading-7 whitespace-pre-line" style="color: #aaa;">{{ data.full_synopsis }}</p>
        </div>
      </div>

      <!-- Right Column: AI Analysis -->
      <div class="lg:col-span-2">
        <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-6 sticky top-4">
          <!-- Header -->
          <div class="flex items-center gap-2.5 mb-6">
            <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: rgba(99, 102, 241, 0.15);">
              <svg class="w-4 h-4" style="color: #6366F1;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 class="text-sm font-semibold text-white">AI分析摘要</h3>
          </div>

          <!-- Score Bars -->
          <div class="space-y-5">
            <div v-for="dim in analysisDimensions" :key="dim.key">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm" style="color: #888;">{{ dim.label }}</span>
                <span class="text-sm font-semibold" :style="{ color: dim.color }">{{ dim.score }}</span>
              </div>
              <div class="h-1.5 rounded-full overflow-hidden" style="background: #2A2A2A;">
                <div
                  class="h-full rounded-full transition-all duration-700"
                  :style="{ width: dim.score + '%', background: dim.color }"
                ></div>
              </div>
            </div>
          </div>

          <!-- Summary Text -->
          <div class="mt-6 p-4 rounded-xl" style="background: #1C1C1C;">
            <p class="text-xs leading-5" style="color: #888;">
              {{ analysisSummary }}
            </p>
          </div>

          <!-- Generate Report Button -->
          <button
            class="w-full mt-5 py-3 rounded-xl text-sm font-bold transition-all hover:opacity-90"
            style="background: #FFE500; color: #000;"
            @click="$emit('switch-section', 'emotion_curve')"
          >
            生成深度分析报告
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

interface OverviewData {
  one_sentence_summary?: string | null
  target_audience?: string | null
  genre?: string | null
  style?: string | null
  tone?: string | null
  full_synopsis?: string | null
}

interface ChapterItem {
  chapter_number: number
  title: string
  summary?: string
  content?: string | null
  word_count?: number
  generation_status?: string
  version_metadata?: Array<{
    ai_review?: {
      is_best?: boolean
      scores?: Record<string, number>
    }
  }> | null
  recommended_version_index?: number | null
  updated_at?: string
  created_at?: string
}

interface CharacterItem {
  name?: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
}

interface AnalysisData {
  overall_score: number
  dimensions: Record<string, number>
  reviewed_chapters: number
}

const props = defineProps<{
  data: OverviewData | null
  chapters?: ChapterItem[]
  characters?: CharacterItem[]
  totalOutlines?: number
  editable?: boolean
  isLoading?: boolean
  projectId?: string
  isCompleted?: boolean
  analysisData?: AnalysisData | null
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'switch-section', section: string): void
  (e: 'toggle-completed', isCompleted: boolean): void
}>()

const completedToggling = ref(false)
const localCompleted = ref(props.isCompleted ?? false)

watch(() => props.isCompleted, (val) => {
  localCompleted.value = val ?? false
})

const toggleCompleted = async () => {
  if (completedToggling.value) return
  completedToggling.value = true
  const newVal = !localCompleted.value
  localCompleted.value = newVal
  emit('toggle-completed', newVal)
  completedToggling.value = false
}

const chapterColors = [
  { bg: 'rgba(168, 85, 247, 0.2)', text: '#A855F7' },
  { bg: 'rgba(99, 102, 241, 0.2)', text: '#6366F1' },
  { bg: 'rgba(46, 213, 115, 0.2)', text: '#2ED573' },
  { bg: 'rgba(255, 229, 0, 0.2)', text: '#FFE500' },
  { bg: 'rgba(0, 180, 216, 0.2)', text: '#00B4D8' },
]

const completedChapters = computed(() => {
  if (!props.chapters) return 0
  return props.chapters.filter(c => c.generation_status === 'successful').length
})

const totalWords = computed(() => {
  if (!props.chapters) return 0
  return props.chapters.reduce((sum, c) => sum + (c.word_count || 0), 0)
})

const aiRate = computed(() => {
  if (!props.chapters || completedChapters.value === 0) return 0
  const total = props.totalOutlines || completedChapters.value
  if (total === 0) return 0
  return Math.min(100, Math.round((completedChapters.value / total) * 100))
})

const avgQuality = computed(() => {
  if (props.analysisData?.overall_score) return props.analysisData.overall_score
  if (!props.chapters) return 0
  const scores: number[] = []
  for (const ch of props.chapters) {
    const s = getChapterScore(ch)
    if (s !== null && s > 0) scores.push(s)
  }
  if (scores.length === 0) {
    const dims = computeAnalysisScores()
    const vals = [dims.pacing, dims.character, dims.worldbuilding, dims.tension].filter(v => v > 0)
    return vals.length > 0 ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0
  }
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
})

const recentChapters = computed(() => {
  if (!props.chapters) return []
  return props.chapters
    .filter(c => c.generation_status === 'successful')
    .sort((a, b) => b.chapter_number - a.chapter_number)
    .slice(0, 3)
})

const displayCharacters = computed(() => {
  if (!props.characters) return []
  return props.characters.slice(0, 4)
})

const analysisDimensions = computed(() => {
  const scores = computeAnalysisScores()
  return [
    { key: 'pacing', label: '故事节奏', score: scores.pacing, color: '#FFE500' },
    { key: 'character', label: '人物塑造', score: scores.character, color: '#A855F7' },
    { key: 'worldbuilding', label: '世界观构建', score: scores.worldbuilding, color: '#00CED1' },
    { key: 'tension', label: '情节张力', score: scores.tension, color: '#2ED573' },
  ]
})

const analysisSummary = computed(() => {
  if (completedChapters.value === 0) {
    return '暂无足够的章节数据进行分析。请先生成章节内容。'
  }

  const dims = analysisDimensions.value
  const hasScores = dims.some(d => d.score > 0)

  if (!hasScores) {
    return `已完成${completedChapters.value}章，共${formatNumber(totalWords.value)}字。点击下方按钮获取AI深度分析。`
  }

  const parts: string[] = []
  const quality = avgQuality.value
  if (quality >= 85) parts.push('整体质量优秀')
  else if (quality >= 70) parts.push('整体质量良好')
  else if (quality >= 50) parts.push('整体质量中等')
  else parts.push('整体质量有提升空间')

  const sorted = [...dims].sort((a, b) => b.score - a.score)
  if (sorted[0].score > 0) parts.push(`${sorted[0].label}表现突出`)
  if (sorted[sorted.length - 1].score > 0 && sorted[sorted.length - 1].score < sorted[0].score) {
    parts.push(`建议加强${sorted[sorted.length - 1].label}`)
  }

  if (props.analysisData?.reviewed_chapters) {
    parts.push(`基于${props.analysisData.reviewed_chapters}章审核数据`)
  }

  return parts.join('，') + '。'
})

function computeAnalysisScores() {
  const defaults = { pacing: 0, character: 0, worldbuilding: 0, tension: 0 }

  // Priority 1: Use aggregated ChapterReview data (six-dimension gatekeeper scores)
  if (props.analysisData?.dimensions) {
    const d = props.analysisData.dimensions
    return {
      pacing: d.pacing || 0,
      character: d.character_depth || 0,
      worldbuilding: Math.round(((d.consistency || 0) + (d.prose_quality || 0)) / 2) || 0,
      tension: Math.round(((d.foreshadowing || 0) + (d.emotion_curve || 0)) / 2) || 0,
    }
  }

  if (!props.chapters || props.chapters.length === 0) return defaults

  // Priority 2: Use ai_review scores from version metadata
  const scoreMap: Record<string, number[]> = {
    pacing: [], character: [], worldbuilding: [], tension: []
  }

  const keyMapping: Record<string, string> = {
    pacing: 'pacing', rhythm: 'pacing', '节奏': 'pacing',
    character: 'character', characterization: 'character', character_depth: 'character', '人物': 'character',
    worldbuilding: 'worldbuilding', world: 'worldbuilding', immersion: 'worldbuilding',
    consistency: 'worldbuilding', prose_quality: 'worldbuilding', '世界观': 'worldbuilding',
    tension: 'tension', plot: 'tension', hook: 'tension',
    foreshadowing: 'tension', emotion_curve: 'tension', '张力': 'tension', '情节': 'tension',
  }

  for (const ch of props.chapters) {
    if (!ch.version_metadata?.length) continue
    const selectedIdx = ch.recommended_version_index ?? 0
    const meta = ch.version_metadata[selectedIdx]
    if (!meta?.ai_review?.scores) continue

    for (const [key, val] of Object.entries(meta.ai_review.scores)) {
      if (typeof val !== 'number' || val === 0) continue
      const mapped = keyMapping[key.toLowerCase()]
      if (mapped && scoreMap[mapped]) {
        scoreMap[mapped].push(val)
      }
    }
  }

  const avg = (arr: number[]) => arr.length > 0 ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0

  const result = {
    pacing: avg(scoreMap.pacing),
    character: avg(scoreMap.character),
    worldbuilding: avg(scoreMap.worldbuilding),
    tension: avg(scoreMap.tension),
  }

  // Priority 3: Compute from chapter statistics when no review data exists
  if (result.pacing === 0 && result.character === 0 && result.worldbuilding === 0 && result.tension === 0) {
    const completed = props.chapters.filter(c => c.generation_status === 'successful')
    if (completed.length >= 3) {
      const wordCounts = completed.map(c => c.word_count || 0).filter(w => w > 0)
      if (wordCounts.length >= 3) {
        const mean = wordCounts.reduce((a, b) => a + b, 0) / wordCounts.length
        const variance = wordCounts.reduce((a, w) => a + (w - mean) ** 2, 0) / wordCounts.length
        const cv = Math.sqrt(variance) / mean
        result.pacing = Math.round(Math.max(40, Math.min(95, 95 - cv * 200)))

        const totalOutlines = props.totalOutlines || completed.length
        const completionRate = Math.min(1, completed.length / totalOutlines)
        result.tension = Math.round(Math.max(40, Math.min(90, 50 + completionRate * 40)))

        const avgWords = Math.round(mean)
        result.character = Math.round(Math.max(40, Math.min(90, avgWords >= 3000 && avgWords <= 5000 ? 80 : 60)))
        result.worldbuilding = Math.round(Math.max(40, Math.min(85, 50 + completed.length * 0.5)))
      }
    }
  }

  return result
}

function getChapterScore(chapter: ChapterItem): number | null {
  if (!chapter.version_metadata?.length) return null
  const selectedIdx = chapter.recommended_version_index ?? 0
  const meta = chapter.version_metadata[selectedIdx]
  if (!meta?.ai_review?.scores) return null
  const scores = meta.ai_review.scores
  if (typeof scores.overall === 'number') return Math.round(scores.overall)
  if (typeof scores.total === 'number') return Math.round(scores.total)
  const numericValues = Object.values(scores).filter((v): v is number => typeof v === 'number')
  if (numericValues.length === 0) return null
  return Math.round(numericValues.reduce((a, b) => a + b, 0) / numericValues.length)
}

function formatNumber(num: number): string {
  return num.toLocaleString('en-US')
}

function formatRelativeDate(chapter: ChapterItem): string {
  const dateStr = chapter.updated_at || chapter.created_at
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function scoreColor(score: number): string {
  if (score >= 90) return '#2ED573'
  if (score >= 75) return '#FFE500'
  return '#FF4757'
}

function scoreBackground(score: number): string {
  if (score >= 90) return 'rgba(46, 213, 115, 0.15)'
  if (score >= 75) return 'rgba(255, 229, 0, 0.15)'
  return 'rgba(255, 71, 87, 0.15)'
}

interface RoleStyle {
  avatarBg: string
  tagBg: string
  tagText: string
}

function getRoleStyle(identity?: string): RoleStyle {
  if (!identity) return { avatarBg: '#1C1C1C', tagBg: '#2A2A2A', tagText: '#888' }
  const id = identity.toLowerCase()
  if (id.includes('主角') || id.includes('男主')) return { avatarBg: 'rgba(255, 229, 0, 0.2)', tagBg: 'rgba(255, 229, 0, 0.2)', tagText: '#FFE500' }
  if (id.includes('女主') || id.includes('女')) return { avatarBg: 'rgba(255, 105, 180, 0.2)', tagBg: 'rgba(255, 105, 180, 0.2)', tagText: '#FF69B4' }
  if (id.includes('反派') || id.includes('魔') || id.includes('boss')) return { avatarBg: 'rgba(255, 71, 87, 0.2)', tagBg: 'rgba(255, 71, 87, 0.2)', tagText: '#FF4757' }
  if (id.includes('导师') || id.includes('师') || id.includes('引导') || id.includes('长老') || id.includes('掌门')) return { avatarBg: 'rgba(0, 180, 216, 0.2)', tagBg: 'rgba(0, 180, 216, 0.2)', tagText: '#00B4D8' }
  return { avatarBg: '#1C1C1C', tagBg: '#2A2A2A', tagText: '#888' }
}

function getRoleEmoji(identity?: string): string {
  if (!identity) return '👤'
  const id = identity.toLowerCase()
  if (id.includes('主角') || id.includes('男主')) return '⚔️'
  if (id.includes('女主') || id.includes('女')) return '🌸'
  if (id.includes('反派') || id.includes('魔') || id.includes('boss')) return '🔥'
  if (id.includes('导师') || id.includes('师') || id.includes('引导') || id.includes('长老') || id.includes('掌门')) return '🧙'
  return '👤'
}

function getRoleLabel(identity?: string): string {
  if (!identity) return '角色'
  if (identity.length <= 3) return identity
  const id = identity.toLowerCase()
  if (id.includes('主角') || id.includes('男主')) return '主角'
  if (id.includes('女主')) return '女主'
  if (id.includes('反派')) return '反派'
  if (id.includes('导师') || id.includes('引导')) return '引导者'
  return identity.slice(0, 3)
}

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'OverviewSection'
})
</script>
