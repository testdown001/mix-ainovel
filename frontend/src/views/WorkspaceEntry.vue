<!-- AIMETA P=创作工作台_登录后首页|R=续写入口_创作概览_最近作品_快捷入口|NR=不含小说管理CRUD|E=route:/home#component:WorkspaceEntry|X=ui|A=首页看板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="home-page">
    <div v-if="showModal" class="modal-backdrop" role="presentation" @click.self="closeModal">
      <section
        class="updates-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="updates-title"
      >
        <header class="updates-modal__header">
          <div>
            <p class="eyebrow">PRODUCT UPDATES</p>
            <h2 id="updates-title">系统更新</h2>
          </div>
          <button type="button" class="modal-close" aria-label="关闭更新日志" @click="closeModal">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>

        <div class="updates-modal__body">
          <div v-if="loadingUpdates" class="modal-state">正在加载更新信息…</div>
          <div v-else-if="updatesError" class="modal-state modal-state--error">
            <span>{{ updatesError }}</span>
            <button type="button" @click="loadUpdates">重试</button>
          </div>
          <div v-else-if="updateLogs.length === 0" class="modal-state">暂无更新日志</div>
          <article v-for="log in updateLogs" v-else :key="log.id" class="update-entry">
            <time :datetime="log.created_at">{{ formatUpdateDate(log.created_at) }}</time>
            <div class="update-entry__content" v-html="renderMarkdown(log.content)"></div>
          </article>
        </div>

        <footer class="updates-modal__footer">
          <button type="button" class="secondary-button" @click="closeModal">关闭</button>
        </footer>
      </section>
    </div>

    <AppTopNav :notification-count="updateLogs.length" @notification="openUpdates" />

    <main class="home-shell">
      <section class="page-heading">
        <div>
          <h1>
            {{ greeting }}，<span>{{ authStore.user?.username || '创作者' }}</span>
          </h1>
          <p>今天继续把故事往前推进。</p>
        </div>
        <button type="button" class="primary-button page-heading__action" @click="goToInspiration">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
            <path stroke-linecap="round" d="M12 5v14M5 12h14" />
          </svg>
          开始新作品
        </button>
      </section>

      <section v-if="loadingNovels" class="dashboard-grid" aria-label="正在加载创作工作台">
        <div class="panel continue-skeleton span-8">
          <div class="skeleton skeleton--label"></div>
          <div class="skeleton-row">
            <div class="skeleton skeleton--cover"></div>
            <div class="skeleton-copy">
              <div class="skeleton skeleton--title"></div>
              <div class="skeleton skeleton--line"></div>
              <div class="skeleton skeleton--line skeleton--short"></div>
            </div>
          </div>
        </div>
        <div class="panel overview-skeleton span-4">
          <div class="skeleton skeleton--label"></div>
          <div v-for="item in 3" :key="item" class="skeleton skeleton--stat"></div>
        </div>
      </section>

      <section v-else-if="novelsError" class="panel error-panel">
        <span class="error-panel__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 9v4m0 4h.01M10.3 3.8L2.8 17a2 2 0 001.7 3h15a2 2 0 001.7-3L13.7 3.8a2 2 0 00-3.4 0z"
            />
          </svg>
        </span>
        <div>
          <h2>作品数据加载失败</h2>
          <p>{{ novelsError }}</p>
        </div>
        <button type="button" class="secondary-button" @click="loadNovels">重新加载</button>
      </section>

      <template v-else>
        <section class="dashboard-grid dashboard-grid--primary">
          <article v-if="featuredNovel" class="panel continue-panel span-8">
            <p class="panel-title">继续创作</p>
            <div class="continue-panel__content">
              <div
                class="project-cover project-cover--large"
                :class="coverVariant(0)"
                aria-hidden="true"
              >
                <span>OCTOPUS NOVEL</span>
                <strong>{{ coverTitle(featuredNovel.title) }}</strong>
              </div>

              <div class="continue-panel__body">
                <div>
                  <h2>{{ featuredNovel.title }}</h2>
                  <p class="next-step">{{ nextStepText(featuredNovel) }}</p>
                  <p class="project-meta">
                    {{ chapterProgressText(featuredNovel) }}
                    <span>·</span>
                    {{ formatWordCount(featuredNovel.total_words) }}
                    <span>·</span>
                    {{ formatRelativeTime(featuredNovel.last_edited) }}编辑
                  </p>
                </div>

                <div class="progress-block">
                  <div class="progress-track">
                    <span :style="{ width: `${projectProgress(featuredNovel)}%` }"></span>
                  </div>
                  <strong>{{ projectProgress(featuredNovel) }}%</strong>
                </div>

                <div class="continue-actions">
                  <button
                    type="button"
                    class="primary-button"
                    @click="continueNovel(featuredNovel)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M15.2 5.2l3.6 3.6M16.7 3.7a2.5 2.5 0 113.6 3.6L6.5 21H3v-3.6L16.7 3.7z"
                      />
                    </svg>
                    {{ continueActionLabel(featuredNovel) }}
                  </button>
                  <button
                    type="button"
                    class="secondary-button"
                    @click="viewProjectDetail(featuredNovel.id)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M4 4h10l6 6v10H4V4zm10 0v6h6M8 15h8"
                      />
                    </svg>
                    项目详情
                  </button>
                </div>
              </div>
            </div>
          </article>

          <article v-else class="panel empty-hero span-8">
            <span class="empty-hero__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M9.7 17h4.6M12 3v1m6.4 1.6l-.7.7M21 12h-1M4 12H3m3.3-5.7l-.7-.7m2.8 9.9a5 5 0 117.1 0l-.5.6a3.4 3.4 0 00-1 2.4V19a2 2 0 11-4 0v-.5c0-.9-.4-1.8-1-2.4l-.6-.6z"
                />
              </svg>
            </span>
            <div>
              <p class="eyebrow">YOUR FIRST STORY</p>
              <h2>从一个念头开始你的第一部作品</h2>
              <p>和缪斯聊出故事立项书，逐步锁定世界观、人物与核心冲突。</p>
            </div>
            <button type="button" class="primary-button" @click="goToInspiration">开始构思</button>
          </article>

          <article class="panel overview-panel span-4">
            <p class="panel-title">创作概览</p>
            <div class="stat-list">
              <div class="stat-item">
                <span class="stat-item__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M4 19.5A2.5 2.5 0 016.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"
                    />
                  </svg>
                </span>
                <strong>{{ novels.length }}</strong>
                <span>作品</span>
              </div>
              <div class="stat-item">
                <span class="stat-item__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"
                    />
                  </svg>
                </span>
                <strong>{{ totalChapters }}</strong>
                <span>已写章节</span>
              </div>
              <div class="stat-item">
                <span class="stat-item__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M15.2 5.2l3.6 3.6M16.7 3.7a2.5 2.5 0 113.6 3.6L6.5 21H3v-3.6L16.7 3.7z"
                    />
                  </svg>
                </span>
                <strong>{{ formatCompactNumber(totalWords) }}</strong>
                <span>总字数</span>
              </div>
            </div>
          </article>
        </section>

        <section class="dashboard-grid dashboard-grid--secondary">
          <article class="panel recent-panel span-8">
            <header class="panel-header">
              <p class="panel-title">最近作品</p>
              <button
                v-if="novels.length > 0"
                type="button"
                class="text-button"
                @click="goToWorkspace"
              >
                查看全部作品
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 18l6-6-6-6" />
                </svg>
              </button>
            </header>

            <div v-if="recentNovels.length === 0" class="recent-empty">
              <p>这里会显示你最近编辑的作品。</p>
            </div>

            <div v-else class="project-list">
              <article v-for="(novel, index) in recentNovels" :key="novel.id" class="project-row">
                <div
                  class="project-cover project-cover--small"
                  :class="coverVariant(index)"
                  aria-hidden="true"
                >
                  <strong>{{ coverTitle(novel.title) }}</strong>
                </div>

                <button
                  type="button"
                  class="project-row__identity"
                  @click="viewProjectDetail(novel.id)"
                >
                  <strong>{{ novel.title }}</strong>
                  <span>
                    {{ chapterProgressText(novel) }}
                    <i>·</i>
                    {{ formatWordCount(novel.total_words) }}
                    <i>·</i>
                    {{ formatRelativeTime(novel.last_edited) }}编辑
                  </span>
                </button>

                <div class="project-row__progress" aria-label="作品完成进度">
                  <strong>{{ projectProgress(novel) }}%</strong>
                  <div class="mini-progress">
                    <span :style="{ width: `${projectProgress(novel)}%` }"></span>
                  </div>
                </div>

                <button type="button" class="continue-small" @click="continueNovel(novel)">
                  {{ isInspirationDraft(novel) ? '构思' : '继续' }}
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 18l6-6-6-6" />
                  </svg>
                </button>
              </article>
            </div>
          </article>

          <aside class="side-rail span-4">
            <section class="panel quick-panel">
              <p class="panel-title">快捷入口</p>
              <div class="quick-grid">
                <button type="button" class="quick-action" @click="goToInspiration">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M9.7 17h4.6M12 3v1m6.4 1.6l-.7.7M21 12h-1M4 12H3m3.3-5.7l-.7-.7m2.8 9.9a5 5 0 117.1 0l-.5.6a3.4 3.4 0 00-1 2.4V19a2 2 0 11-4 0v-.5c0-.9-.4-1.8-1-2.4l-.6-.6z"
                    />
                  </svg>
                  <span>灵感构思</span>
                </button>
                <button
                  type="button"
                  class="quick-action"
                  :disabled="isImporting"
                  @click="triggerImport"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M12 3v12m0 0l-4-4m4 4l4-4M5 19h14"
                    />
                  </svg>
                  <span>{{ isImporting ? '正在导入' : '导入小说' }}</span>
                </button>
                <button type="button" class="quick-action" @click="goToWorkspace">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M4 5h16v14H4zM8 9h8M8 13h8"
                    />
                  </svg>
                  <span>全部作品</span>
                </button>
              </div>
              <input
                ref="fileInput"
                type="file"
                accept=".txt"
                class="visually-hidden"
                @change="handleFileImport"
              />
              <p v-if="importMessage" class="import-message">{{ importMessage }}</p>
            </section>

            <button type="button" class="panel update-digest" @click="openUpdates">
              <span class="panel-title">系统更新</span>
              <span v-if="loadingUpdates" class="update-digest__body">正在获取更新信息…</span>
              <span v-else-if="updatesError" class="update-digest__body">更新信息暂时不可用</span>
              <span v-else-if="latestUpdate" class="update-digest__body">
                <strong>{{ extractTitle(latestUpdate.content) }}</strong>
                <small>{{ formatUpdateDate(latestUpdate.created_at) }}</small>
              </span>
              <span v-else class="update-digest__body update-digest__empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M8 2v3m8-3v3M4 9h16M5 5h14a1 1 0 011 1v14H4V6a1 1 0 011-1z"
                  />
                </svg>
                暂无重要更新
              </span>
            </button>
          </aside>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { marked } from 'marked'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getLatestUpdates } from '@/api/updates'
import { NovelAPI } from '@/api/novel'
import { formatRelativeTime } from '@/utils/date'
import AppTopNav from '@/components/shared/AppTopNav.vue'
import type { UpdateLog } from '@/api/updates'
import type { NovelProjectSummary } from '@/api/novel'

marked.setOptions({ gfm: true, breaks: true })

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const showModal = ref(false)
const updateLogs = ref<UpdateLog[]>([])
const novels = ref<NovelProjectSummary[]>([])
const loadingNovels = ref(true)
const loadingUpdates = ref(true)
const novelsError = ref('')
const updatesError = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const isImporting = ref(false)
const importMessage = ref('')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '深夜好'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const featuredNovel = computed(() => novels.value[0] ?? null)
const recentNovels = computed(() => novels.value.slice(0, 4))
const latestUpdate = computed(() => updateLogs.value[0] ?? null)
const totalChapters = computed(() =>
  novels.value.reduce((total, novel) => total + (novel.completed_chapters || 0), 0),
)
const totalWords = computed(() =>
  novels.value.reduce((total, novel) => total + (novel.total_words || 0), 0),
)

const renderMarkdown = (markdown: string) => marked.parse(markdown) as string

const extractTitle = (content: string) => {
  const heading = content.match(/^#+\s*(.+)$/m)?.[1]?.trim()
  const firstLine = content
    .replace(/^#+\s*/gm, '')
    .split('\n')
    .find((line) => line.trim())
    ?.trim()
  return heading || firstLine || '产品更新'
}

const formatUpdateDate = (date: string) =>
  new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric' }).format(new Date(date))

const formatCompactNumber = (value: number) => {
  if (value < 10_000) return value.toLocaleString('zh-CN')
  const digits = value >= 100_000 ? 0 : 1
  return `${(value / 10_000).toFixed(digits).replace(/\.0$/, '')}万`
}

const formatWordCount = (value = 0) => `${formatCompactNumber(value)}字`

const projectProgress = (novel: NovelProjectSummary) => {
  if (novel.is_completed) return 100
  if (!novel.total_chapters) return 0
  return Math.min(100, Math.round((novel.completed_chapters / novel.total_chapters) * 100))
}

const chapterProgressText = (novel: NovelProjectSummary) => {
  if (!novel.total_chapters) return '尚未生成章节规划'
  return `${novel.completed_chapters} / ${novel.total_chapters} 章`
}

const isInspirationDraft = (novel: NovelProjectSummary) =>
  novel.title === '未命名灵感' || novel.total_chapters === 0

const nextStepText = (novel: NovelProjectSummary) => {
  if (isInspirationDraft(novel)) return '继续完善故事构思'
  if (novel.is_completed) return '作品已完结，可以继续查看和打磨'
  if (novel.next_chapter_number) {
    return `下一章  第${novel.next_chapter_number}章${novel.next_chapter_title ? ` · ${novel.next_chapter_title}` : ''}`
  }
  return '当前章节规划已完成'
}

const continueActionLabel = (novel: NovelProjectSummary) =>
  isInspirationDraft(novel) ? '继续构思' : novel.is_completed ? '查看作品' : '继续写作'

const coverTitle = (title: string) => title.replace(/[：:]/g, '\n').slice(0, 18)
const coverVariant = (index: number) => `project-cover--variant-${index % 3}`

const loadNovels = async () => {
  loadingNovels.value = true
  novelsError.value = ''
  try {
    novels.value = await NovelAPI.getAllNovels()
  } catch (error) {
    novelsError.value = error instanceof Error ? error.message : '请稍后重试'
  } finally {
    loadingNovels.value = false
  }
}

const loadUpdates = async () => {
  loadingUpdates.value = true
  updatesError.value = ''
  try {
    updateLogs.value = await getLatestUpdates()
    if (route.query.updates === '1') showModal.value = true
  } catch (error) {
    updatesError.value = error instanceof Error ? error.message : '请稍后重试'
  } finally {
    loadingUpdates.value = false
  }
}

const openUpdates = () => {
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  if (route.query.updates === '1') {
    router.replace({ path: '/home' })
  }
}

const continueNovel = (novel: NovelProjectSummary) => {
  if (isInspirationDraft(novel)) {
    router.push({ path: '/inspiration', query: { project_id: novel.id } })
    return
  }
  router.push(`/novel/${novel.id}`)
}

const viewProjectDetail = (projectId: string) => router.push(`/detail/${projectId}`)
const goToInspiration = () => router.push('/inspiration')
const goToWorkspace = () => router.push('/workspace')

const triggerImport = () => {
  if (!isImporting.value) fileInput.value?.click()
}

const handleFileImport = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  importMessage.value = ''
  if (!file.name.toLowerCase().endsWith('.txt')) {
    importMessage.value = '请上传 .txt 格式的小说文件'
    input.value = ''
    return
  }

  isImporting.value = true
  try {
    const project = await NovelAPI.importNovel(file)
    await loadNovels()
    router.push(`/novel/${project.id}`)
  } catch (error) {
    importMessage.value = error instanceof Error ? error.message : '导入失败，请重试'
  } finally {
    isImporting.value = false
    input.value = ''
  }
}

onMounted(() => {
  void Promise.all([loadNovels(), loadUpdates()])
})
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  color: var(--md-on-background);
  background: var(--md-background);
  font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
}

.home-shell {
  width: min(100% - 48px, 1440px);
  margin: 0 auto;
  padding: 38px 0 56px;
}

.page-heading {
  min-height: 90px;
  margin-bottom: 26px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.page-heading h1 {
  margin: 0 0 7px;
  font-size: clamp(30px, 3vw, 42px);
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1.18;
}

.page-heading h1 span {
  color: var(--md-primary);
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
}

.page-heading p {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: 16px;
}

.page-heading__action {
  margin-top: 10px;
  flex-shrink: 0;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 20px;
}

.dashboard-grid--primary {
  align-items: stretch;
}

.dashboard-grid--secondary {
  margin-top: 20px;
  align-items: start;
}

.span-8 {
  grid-column: span 8;
}

.span-4 {
  grid-column: span 4;
}

.panel {
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-lg);
  background: var(--md-surface);
}

.panel-title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.panel-header {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.primary-button,
.secondary-button {
  min-height: 44px;
  padding: 0 18px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 700;
  transition:
    transform var(--md-duration-medium) var(--md-easing-standard),
    border-color var(--md-duration-medium),
    background var(--md-duration-medium),
    color var(--md-duration-medium);
}

.primary-button {
  border: 1px solid var(--md-primary);
  color: var(--md-on-primary);
  background: var(--md-primary);
}

.primary-button:hover {
  background: var(--md-primary-light);
  transform: translateY(-1px);
}

.secondary-button {
  border: 1px solid var(--md-outline);
  color: var(--md-on-surface);
  background: transparent;
}

.secondary-button:hover {
  border-color: var(--md-secondary-dark);
  background: var(--md-surface-container);
}

.primary-button svg,
.secondary-button svg {
  width: 17px;
  height: 17px;
}

.continue-panel {
  min-height: 380px;
  padding: 28px 30px;
  overflow: hidden;
}

.continue-panel__content {
  height: calc(100% - 42px);
  margin-top: 22px;
  display: grid;
  grid-template-columns: 164px minmax(0, 1fr);
  align-items: stretch;
  gap: 34px;
}

.continue-panel__body {
  min-width: 0;
  padding: 14px 0 2px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.continue-panel__body h2 {
  margin: 0;
  overflow: hidden;
  color: var(--md-on-surface);
  font-size: clamp(21px, 2.1vw, 28px);
  font-weight: 800;
  letter-spacing: -0.035em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.next-step {
  margin: 16px 0 0;
  color: var(--md-on-secondary-container);
  font-size: 17px;
  font-weight: 600;
}

.project-meta {
  margin: 24px 0 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.project-cover {
  position: relative;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--md-primary) 24%, var(--md-outline));
  color: var(--md-primary);
  background-color: #0d0d0d;
  background-image:
    linear-gradient(145deg, transparent 22%, rgba(255, 229, 0, 0.82) 23% 26%, transparent 27%),
    linear-gradient(160deg, transparent 48%, rgba(255, 229, 0, 0.28) 49% 55%, transparent 56%),
    radial-gradient(circle at 80% 15%, rgba(255, 229, 0, 0.18), transparent 32%);
  box-shadow: inset 0 0 40px rgba(255, 229, 0, 0.03);
}

.project-cover::after {
  position: absolute;
  inset: 0;
  content: '';
  opacity: 0.2;
  background-image: repeating-linear-gradient(
    115deg,
    transparent 0 9px,
    rgba(255, 255, 255, 0.08) 10px,
    transparent 11px
  );
}

.project-cover--variant-1 {
  color: #ffdb72;
  background-image:
    linear-gradient(155deg, transparent 35%, rgba(255, 180, 0, 0.68) 36% 39%, transparent 40%),
    linear-gradient(30deg, transparent 48%, rgba(255, 229, 0, 0.18) 49% 60%, transparent 61%),
    radial-gradient(circle at 25% 30%, rgba(255, 229, 0, 0.18), transparent 34%);
}

.project-cover--variant-2 {
  color: #fff062;
  background-image:
    linear-gradient(125deg, transparent 15%, rgba(255, 229, 0, 0.55) 16% 18%, transparent 19%),
    linear-gradient(170deg, transparent 55%, rgba(255, 229, 0, 0.28) 56% 68%, transparent 69%),
    radial-gradient(circle at 80% 75%, rgba(255, 229, 0, 0.16), transparent 35%);
}

.project-cover--large {
  min-height: 268px;
  padding: 18px 15px;
  border-radius: 13px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.project-cover--large span {
  position: relative;
  z-index: 1;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.project-cover--large strong,
.project-cover--small strong {
  position: relative;
  z-index: 1;
  white-space: pre-line;
}

.project-cover--large strong {
  font-size: 16px;
  line-height: 1.45;
}

.progress-block {
  display: flex;
  align-items: center;
  gap: 14px;
}

.progress-block strong {
  min-width: 36px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 15px;
}

.progress-track,
.mini-progress {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--md-surface-container-high);
}

.progress-track {
  flex: 1;
}

.progress-track span,
.mini-progress span {
  height: 100%;
  display: block;
  border-radius: inherit;
  background: var(--md-primary);
  transition: width var(--md-duration-long) var(--md-easing-decelerate);
}

.continue-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.overview-panel {
  min-height: 380px;
  padding: 28px;
}

.stat-list {
  margin-top: 22px;
  display: grid;
  gap: 12px;
}

.stat-item {
  min-height: 78px;
  padding: 14px 18px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-md);
  display: grid;
  grid-template-columns: 42px minmax(56px, auto) 1fr;
  align-items: center;
  gap: 14px;
  background: var(--md-surface-container);
}

.stat-item__icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--md-primary);
  background: var(--md-surface-dim);
}

.stat-item__icon svg {
  width: 20px;
  height: 20px;
}

.stat-item strong {
  color: var(--md-on-surface);
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
  font-size: clamp(25px, 2vw, 34px);
  line-height: 1;
}

.stat-item > span:last-child {
  justify-self: end;
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.empty-hero {
  min-height: 380px;
  padding: 42px;
  display: flex;
  align-items: center;
  gap: 26px;
}

.empty-hero__icon {
  width: 76px;
  height: 76px;
  border-radius: var(--md-radius-lg);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: var(--md-primary);
  background: var(--md-primary-container);
}

.empty-hero__icon svg {
  width: 36px;
  height: 36px;
}

.empty-hero > div {
  flex: 1;
}

.empty-hero h2 {
  margin: 5px 0 8px;
  font-size: 26px;
}

.empty-hero p:not(.eyebrow) {
  max-width: 540px;
  margin: 0;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
}

.eyebrow {
  margin: 0;
  color: var(--md-primary);
  font-family: 'Space Grotesk', sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.recent-panel {
  min-height: 300px;
  padding: 24px 30px 18px;
}

.text-button {
  padding: 6px 0;
  border: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--md-primary);
  background: transparent;
  font-size: 13px;
  font-weight: 600;
}

.text-button svg {
  width: 16px;
  height: 16px;
}

.project-list {
  display: grid;
}

.project-row {
  min-height: 100px;
  padding: 16px 0;
  border-top: 1px solid var(--md-outline);
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) minmax(160px, 0.34fr) 104px;
  align-items: center;
  gap: 20px;
}

.project-list .project-row:first-child {
  border-top-color: transparent;
}

.project-cover--small {
  width: 58px;
  height: 70px;
  padding: 7px;
  border-radius: 8px;
  display: flex;
  align-items: flex-end;
}

.project-cover--small strong {
  overflow: hidden;
  font-size: 8px;
  line-height: 1.3;
}

.project-row__identity {
  min-width: 0;
  padding: 8px 0;
  border: 0;
  display: grid;
  gap: 8px;
  color: inherit;
  background: transparent;
  text-align: left;
}

.project-row__identity > strong {
  overflow: hidden;
  color: var(--md-on-surface);
  font-size: 15px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-row__identity > span {
  overflow: hidden;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-row__identity i {
  margin: 0 5px;
  font-style: normal;
}

.project-row__progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.project-row__progress strong {
  min-width: 34px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 12px;
}

.mini-progress {
  flex: 1;
  height: 5px;
}

.continue-small {
  min-height: 40px;
  padding: 0 15px;
  border: 1px solid var(--md-outline);
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: var(--md-primary);
  background: transparent;
  font-size: 13px;
  font-weight: 700;
  transition:
    border-color var(--md-duration-medium),
    background var(--md-duration-medium);
}

.continue-small:hover {
  border-color: color-mix(in srgb, var(--md-primary) 40%, var(--md-outline));
  background: var(--md-primary-container);
}

.continue-small svg {
  width: 15px;
  height: 15px;
}

.recent-empty {
  min-height: 210px;
  display: grid;
  place-items: center;
  color: var(--md-on-surface-variant);
}

.side-rail {
  display: grid;
  gap: 16px;
}

.quick-panel {
  padding: 24px 26px;
}

.quick-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.quick-action {
  min-height: 92px;
  padding: 13px 8px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-md);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--md-on-secondary-container);
  background: var(--md-surface-container);
  font-size: 12px;
  transition:
    border-color var(--md-duration-medium),
    color var(--md-duration-medium),
    transform var(--md-duration-medium);
}

.quick-action:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--md-primary) 35%, var(--md-outline));
  color: var(--md-on-surface);
  transform: translateY(-1px);
}

.quick-action:disabled {
  opacity: 0.6;
}

.quick-action svg {
  width: 26px;
  height: 26px;
  color: var(--md-primary);
}

.import-message {
  margin: 12px 0 0;
  color: var(--md-error);
  font-size: 12px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.update-digest {
  width: 100%;
  min-height: 118px;
  padding: 21px 26px;
  display: grid;
  align-content: start;
  gap: 13px;
  color: inherit;
  text-align: left;
  transition:
    border-color var(--md-duration-medium),
    background var(--md-duration-medium);
}

.update-digest:hover {
  border-color: var(--md-secondary-dark);
  background: var(--md-surface-container-low);
}

.update-digest__body {
  display: grid;
  gap: 5px;
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.update-digest__body strong {
  overflow: hidden;
  color: var(--md-on-secondary-container);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.update-digest__body small {
  font-size: 11px;
}

.update-digest__empty {
  grid-template-columns: 20px 1fr;
  align-items: center;
}

.update-digest__empty svg {
  width: 18px;
  height: 18px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  padding: 24px;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.76);
  backdrop-filter: blur(6px);
}

.updates-modal {
  width: min(680px, 100%);
  max-height: min(760px, 88vh);
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-lg);
  display: flex;
  flex-direction: column;
  background: var(--md-surface);
  box-shadow: var(--md-elevation-5);
}

.updates-modal__header,
.updates-modal__footer {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.updates-modal__header {
  border-bottom: 1px solid var(--md-outline);
}

.updates-modal__header h2 {
  margin: 4px 0 0;
  font-size: 20px;
}

.modal-close {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: var(--md-radius-sm);
  display: grid;
  place-items: center;
  color: var(--md-on-surface-variant);
  background: transparent;
}

.modal-close:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

.modal-close svg {
  width: 20px;
  height: 20px;
}

.updates-modal__body {
  padding: 22px 24px;
  overflow-y: auto;
  display: grid;
  gap: 14px;
}

.updates-modal__footer {
  border-top: 1px solid var(--md-outline);
  justify-content: flex-end;
}

.update-entry {
  padding: 18px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-md);
  background: var(--md-surface-container);
}

.update-entry time {
  color: var(--md-on-surface-variant);
  font-size: 11px;
}

.update-entry__content {
  margin-top: 9px;
  color: var(--md-on-secondary-container);
  font-size: 13px;
  line-height: 1.75;
}

.update-entry__content :deep(h1),
.update-entry__content :deep(h2),
.update-entry__content :deep(h3),
.update-entry__content :deep(p) {
  margin: 0 0 8px;
}

.update-entry__content :deep(*:last-child) {
  margin-bottom: 0;
}

.modal-state {
  min-height: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--md-on-surface-variant);
}

.modal-state--error {
  color: var(--md-error);
}

.modal-state button {
  padding: 7px 14px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

.error-panel {
  min-height: 240px;
  padding: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 22px;
}

.error-panel__icon {
  width: 56px;
  height: 56px;
  border-radius: var(--md-radius-md);
  display: grid;
  place-items: center;
  color: var(--md-error);
  background: var(--md-error-container);
}

.error-panel__icon svg {
  width: 27px;
  height: 27px;
}

.error-panel > div {
  max-width: 520px;
}

.error-panel h2,
.error-panel p {
  margin: 0;
}

.error-panel p {
  margin-top: 6px;
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.skeleton {
  border-radius: 8px;
  background: linear-gradient(
    90deg,
    var(--md-surface-container) 25%,
    var(--md-surface-container-high) 50%,
    var(--md-surface-container) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-pulse 1.5s infinite linear;
}

.continue-skeleton,
.overview-skeleton {
  min-height: 380px;
  padding: 28px;
}

.skeleton--label {
  width: 100px;
  height: 18px;
}

.skeleton-row {
  margin-top: 26px;
  display: flex;
  gap: 30px;
}

.skeleton--cover {
  width: 160px;
  height: 268px;
  flex-shrink: 0;
}

.skeleton-copy {
  flex: 1;
  padding-top: 16px;
}

.skeleton--title {
  width: 76%;
  height: 28px;
}

.skeleton--line {
  width: 90%;
  height: 14px;
  margin-top: 22px;
}

.skeleton--short {
  width: 54%;
}

.skeleton--stat {
  height: 78px;
  margin-top: 14px;
}

@keyframes skeleton-pulse {
  to {
    background-position: -200% 0;
  }
}

@media (max-width: 1100px) {
  .span-8,
  .span-4 {
    grid-column: span 12;
  }

  .overview-panel {
    min-height: auto;
  }

  .stat-list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .stat-item {
    grid-template-columns: 42px 1fr;
  }

  .stat-item > span:last-child {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .side-rail {
    grid-template-columns: minmax(0, 1fr) minmax(280px, 0.65fr);
  }
}

@media (max-width: 760px) {
  .home-shell {
    width: calc(100% - 32px);
    padding-top: 28px;
  }

  .page-heading {
    margin-bottom: 22px;
    display: grid;
  }

  .page-heading__action {
    width: 100%;
    margin-top: 0;
  }

  .continue-panel,
  .overview-panel,
  .recent-panel,
  .quick-panel {
    padding: 22px;
  }

  .continue-panel__content {
    grid-template-columns: 92px minmax(0, 1fr);
    gap: 18px;
  }

  .project-cover--large {
    min-height: 154px;
    padding: 10px;
  }

  .project-cover--large strong {
    font-size: 11px;
  }

  .continue-panel__body {
    padding-top: 4px;
  }

  .project-meta {
    margin-top: 16px;
  }

  .progress-block,
  .continue-actions {
    grid-column: 1 / -1;
  }

  .stat-list,
  .side-rail {
    grid-template-columns: 1fr;
  }

  .stat-item {
    grid-template-columns: 42px minmax(56px, auto) 1fr;
  }

  .stat-item > span:last-child {
    grid-column: auto;
    justify-self: end;
  }

  .project-row {
    grid-template-columns: 48px minmax(0, 1fr) auto;
    gap: 13px;
  }

  .project-cover--small {
    width: 48px;
    height: 60px;
  }

  .project-row__progress {
    display: none;
  }

  .continue-small {
    width: 44px;
    padding: 0;
    font-size: 0;
  }

  .continue-small svg {
    width: 18px;
    height: 18px;
  }

  .empty-hero {
    min-height: 360px;
    padding: 30px;
    flex-direction: column;
    align-items: flex-start;
  }

  .empty-hero .primary-button {
    width: 100%;
  }

  .error-panel {
    padding: 30px;
    flex-direction: column;
    text-align: center;
  }
}

@media (max-width: 520px) {
  .continue-panel__content {
    height: auto;
    display: grid;
  }

  .continue-panel__body {
    display: contents;
  }

  .continue-panel__body > div:first-child {
    align-self: center;
  }

  .continue-panel__body h2 {
    white-space: normal;
  }

  .next-step {
    margin-top: 10px;
    font-size: 14px;
  }

  .project-meta {
    font-size: 11px;
  }

  .progress-block {
    margin-top: 20px;
  }

  .continue-actions .primary-button,
  .continue-actions .secondary-button {
    flex: 1;
    padding: 0 12px;
  }

  .quick-grid {
    grid-template-columns: 1fr;
  }

  .quick-action {
    min-height: 58px;
    padding: 10px 14px;
    flex-direction: row;
    justify-content: flex-start;
  }

  .quick-action svg {
    width: 22px;
    height: 22px;
  }

  .project-row__identity > span {
    white-space: normal;
  }

  .modal-backdrop {
    padding: 12px;
  }
}
</style>
