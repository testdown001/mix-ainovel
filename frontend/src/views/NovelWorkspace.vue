<!-- AIMETA P=小说工作区_小说列表管理|R=小说列表_创建|NR=不含章节编辑|E=route:/workspace#component:NovelWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="workspace-root">
    <transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0 translate-y-4"
      leave-to-class="opacity-0 translate-y-4"
    >
      <div v-if="deleteMessage" class="md-snackbar">
        <span class="neon-pulse" :class="deleteMessage.type === 'success' ? '' : 'neon-pulse-primary'"></span>
        <span class="md-snackbar-text">{{ deleteMessage.text }}</span>
      </div>
    </transition>

    <div class="workspace-layout">
      <!-- Sidebar -->
      <aside class="workspace-sidebar">
        <div class="sidebar-section-label">小说管理</div>
        <div class="sidebar-novel-switcher">
          当前作品列表
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        <div class="sidebar-novels">
          <div
            v-for="project in novelStore.projects"
            :key="project.id"
            class="sidebar-novel-item"
            :class="{ 'sidebar-novel-item--active': selectedProjectId === project.id }"
            @click="selectProject(project)"
          >
            <span class="sidebar-novel-icon">📄</span>
            <span class="sidebar-novel-name">{{ project.title }}</span>
          </div>
        </div>

        <div class="sidebar-nav">
          <div class="sidebar-section-label">功能导航</div>
          <button class="sidebar-nav-item" @click="goToInspiration">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
            创作空间
          </button>
          <button class="sidebar-nav-item">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/></svg>
            数据分析
          </button>
          <button class="sidebar-nav-item">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"/><path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6z"/></svg>
            订阅方案
          </button>
        </div>

        <div class="sidebar-bottom">
          <button class="sidebar-cta" @click="goToInspiration">
            + 新建小说
          </button>
          <div class="sidebar-footer-links">
            <button class="sidebar-footer-link" @click="router.push('/settings')">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              系统设置
            </button>
            <button class="sidebar-footer-link">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"/></svg>
              帮助中心
            </button>
          </div>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="workspace-main">
        <!-- Welcome Banner + AI Status -->
        <div class="welcome-row">
          <div class="welcome-section">
            <h1 class="welcome-title">欢迎回来, 创作者</h1>
            <p class="welcome-subtitle">今天是 {{ todayDate }}，你的故事正在散发光芒。</p>
          </div>
          <div class="ai-status-card">
            <div class="ai-status-header">
              <span class="neon-pulse"></span>
              <span class="ai-status-label">ARBORIS AI V4.0</span>
              <span class="ai-status-latency">Latency: 24ms</span>
            </div>
            <div class="ai-status-row">
              <span>Context Window (128k)</span>
              <span class="text-secondary">85% Available</span>
            </div>
            <div class="ai-status-bar">
              <div class="ai-status-bar-fill" style="width: 85%"></div>
            </div>
            <div class="ai-status-row mt-2">
              <span>Tokens Remaining</span>
              <span class="ai-status-tokens">1,240,500</span>
            </div>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="novelStore.isLoading" class="flex flex-col items-center justify-center py-20">
          <div class="md-spinner"></div>
          <p class="mt-4 text-text-secondary">加载中...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="novelStore.error" class="flex flex-col items-center justify-center py-20">
          <p class="text-error mb-4">{{ novelStore.error }}</p>
          <button @click="loadProjects" class="md-btn md-btn-filled">重试</button>
        </div>

        <template v-else>
          <!-- Stats Row -->
          <div class="stats-row stagger-reveal">
            <div class="stat-card">
              <div class="stat-label">总字数</div>
              <div class="stat-value stat-value--primary">{{ totalWords.toLocaleString() }}</div>
              <div class="stat-trend">↗ 较上周增长 12%</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">已完成章节</div>
              <div class="stat-value">{{ totalChapters }}</div>
              <div class="stat-trend">预计还有 15 章节完结</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">AI生成版本</div>
              <div class="stat-value stat-value--green">{{ totalVersions }}</div>
              <div class="stat-trend">平均每章 {{ avgVersionsPerChapter }} 个版本</div>
            </div>
          </div>

          <!-- Featured Novel + Right Panel -->
          <div class="content-grid">
            <div class="content-left">
              <!-- Featured Novel Card -->
              <div v-if="featuredProject" class="featured-card">
                <div class="featured-tags">
                  <span class="featured-tag">{{ featuredProject.genre || '小说' }}</span>
                  <span class="featured-tag featured-tag--status">
                    <span class="neon-pulse" style="width:6px;height:6px;"></span>
                    进行中
                  </span>
                  <span class="featured-id">ID: {{ featuredProject.id?.slice(0, 8) }}</span>
                </div>
                <h2 class="featured-title font-manuscript">{{ featuredProject.title }}</h2>
                <p class="featured-desc">{{ featuredDesc }}</p>
                <div class="featured-footer">
                  <div class="featured-progress">
                    <div class="progress-ring">
                      <svg viewBox="0 0 60 60" class="w-14 h-14">
                        <circle cx="30" cy="30" r="24" fill="none" stroke="rgba(250,204,21,0.15)" stroke-width="4" />
                        <circle cx="30" cy="30" r="24" fill="none" stroke="#FACC15" stroke-width="4"
                          :stroke-dasharray="progressCircle"
                          stroke-dashoffset="0"
                          stroke-linecap="round"
                          transform="rotate(-90 30 30)" />
                      </svg>
                      <span class="progress-text">{{ progressPercent }}%</span>
                    </div>
                    <div class="progress-info">
                      <span class="progress-label">当前进度</span>
                      <span class="progress-detail">第 {{ selectedSummary?.completed_chapters || 0 }} 章 / 共 {{ selectedSummary?.total_chapters || 0 }} 章</span>
                    </div>
                  </div>
                  <button class="continue-btn" @click="enterProject(featuredProject)">
                    继续写作
                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.042 21.672L13.684 16.6m0 0l-2.51 2.225.569-9.47 5.227 7.917-3.286-.672zM12 2.25V4.5m5.834.166l-1.591 1.591M20.25 10.5H18M7.757 14.743l-1.59 1.59M6 10.5H3.75m4.007-4.243l-1.59-1.59" />
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Setting Library -->
              <div class="setting-library">
                <div class="setting-library-header">
                  <h3 class="setting-library-title">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"/></svg>
                    设定库
                  </h3>
                  <button class="md-btn md-btn-secondary" style="min-height:32px;padding:0 12px;font-size:12px;" @click="featuredProject && viewProjectDetail(featuredProject.id)">管理全部</button>
                </div>
                <div class="setting-categories">
                  <div class="setting-cat">
                    <svg class="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/></svg>
                    <span class="setting-cat-count">{{ characterCount }} 个角色</span>
                    <div class="setting-cat-label">核心角色</div>
                    <div class="setting-cat-desc">{{ characterNames }}</div>
                  </div>
                  <div class="setting-cat">
                    <svg class="w-5 h-5 text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"/></svg>
                    <span class="setting-cat-count">{{ locationCount }} 个地点</span>
                    <div class="setting-cat-label">地理与世界观</div>
                    <div class="setting-cat-desc">{{ locationNames }}</div>
                  </div>
                  <div class="setting-cat">
                    <svg class="w-5 h-5 text-warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"/></svg>
                    <span class="setting-cat-count">{{ relationshipCount }} 组关系</span>
                    <div class="setting-cat-label">角色关系</div>
                    <div class="setting-cat-desc">{{ relationshipDesc }}</div>
                  </div>
                </div>
              </div>

              <!-- Other Project Cards -->
              <div class="projects-grid" v-if="otherProjects.length > 0 || true">
                <ProjectCard
                  v-for="project in otherProjects"
                  :key="project.id"
                  :project="project"
                  @click="enterProject(project)"
                  @detail="viewProjectDetail"
                  @continue="enterProject"
                  @delete="handleDeleteProject"
                />

                <div @click="goToInspiration" class="create-card">
                  <svg class="w-6 h-6 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>创建新项目</span>
                </div>

                <div @click="triggerImport" class="create-card">
                  <div v-if="isImporting" class="flex flex-col items-center gap-2">
                    <div class="md-spinner" style="width:24px;height:24px;"></div>
                    <span>正在导入...</span>
                  </div>
                  <template v-else>
                    <svg class="w-6 h-6 text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    <span>导入小说文件</span>
                  </template>
                </div>
                <input type="file" ref="fileInput" accept=".txt" class="hidden" @change="handleFileImport" />
              </div>
            </div>

            <!-- Right Panel -->
            <div class="content-right">
              <!-- Recent Chapters -->
              <div class="recent-chapters">
                <div class="recent-header">
                  <span class="recent-title">近期章节</span>
                  <button class="recent-view-all" @click="featuredProject && enterProject(featuredProject)">查看全部</button>
                </div>
                <div v-if="loadingDetail" class="recent-loading">加载中...</div>
                <div v-else-if="recentChapters.length === 0" class="recent-empty">暂无已完成章节</div>
                <div v-else class="recent-list">
                  <div class="recent-item" v-for="ch in recentChapters" :key="ch.number">
                    <span class="recent-dot" :class="chapterDotClass(ch.status)"></span>
                    <div class="recent-item-content">
                      <div class="recent-item-title">第{{ ch.number }}章：{{ ch.title }}</div>
                      <div class="recent-item-meta">{{ ch.status === 'successful' ? '已完成' : '草稿' }} · {{ ch.wordCount.toLocaleString() }} 字</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- AI Creative Insight -->
              <div class="ai-insight-card">
                <h4 class="ai-insight-title">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/></svg>
                  AI 创意联想
                </h4>
                <p class="ai-insight-text">基于第42章的内容，建议在下一章中加入关于"数字灵魂"的哲学辩论。甚至可以遇到一个坚信自己有情感的旧服务机器人...</p>
                <button class="ai-insight-link">生成剧情大纲 →</button>
              </div>
            </div>
          </div>
        </template>
      </main>
    </div>

    <!-- Delete Dialog -->
    <transition enter-active-class="transition-opacity duration-200" leave-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-to-class="opacity-0">
      <div v-if="showDeleteDialog" class="md-dialog-overlay">
        <div class="md-dialog max-w-md w-full mx-4">
          <div class="md-dialog-header flex items-center gap-4">
            <div class="w-10 h-10 rounded flex items-center justify-center" style="background-color: var(--ar-error-muted, rgba(239,68,68,0.15));">
              <svg class="w-5 h-5 text-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <div>
              <h3 class="md-dialog-title">确认删除</h3>
              <p class="text-text-muted text-xs">此操作无法撤销</p>
            </div>
          </div>
          <div class="md-dialog-content">
            <p>确定要删除项目 "<strong class="text-primary">{{ projectToDelete?.title }}</strong>" 吗？所有相关数据将被永久删除。</p>
          </div>
          <div class="md-dialog-actions">
            <button @click="cancelDelete" class="md-btn md-btn-text">取消</button>
            <button @click="confirmDelete" :disabled="isDeleting" class="md-btn md-btn-filled" style="background:var(--ar-error);color:#fff;">
              {{ isDeleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import ProjectCard from '@/components/ProjectCard.vue'
import type { NovelProject, NovelProjectSummary } from '@/api/novel'
import { NovelAPI } from '@/api/novel'

const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

const fileInput = ref<HTMLInputElement | null>(null)
const isImporting = ref(false)
const showDeleteDialog = ref(false)
const projectToDelete = ref<NovelProjectSummary | null>(null)
const isDeleting = ref(false)
const deleteMessage = ref<{type: 'success' | 'error', text: string} | null>(null)
const selectedProjectId = ref<string | null>(null)
const selectedProjectDetail = ref<NovelProject | null>(null)
const loadingDetail = ref(false)

const todayDate = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
})

const selectedSummary = computed(() =>
  novelStore.projects.find(p => p.id === selectedProjectId.value) || novelStore.projects[0] || null
)
const featuredProject = computed(() => selectedSummary.value)
const otherProjects = computed(() =>
  novelStore.projects.filter(p => p.id !== selectedProjectId.value)
)
const totalWords = computed(() => {
  const detail = selectedProjectDetail.value
  if (!detail?.chapters?.length) return 0
  return detail.chapters.reduce((sum, ch) => sum + (ch.word_count || 0), 0)
})
const totalChapters = computed(() => selectedSummary.value?.completed_chapters || 0)
const totalVersions = computed(() => {
  const detail = selectedProjectDetail.value
  if (!detail?.chapters?.length) return 0
  return detail.chapters.reduce((sum, ch) => sum + (ch.versions?.length || 0), 0)
})
const avgVersionsPerChapter = computed(() => {
  const detail = selectedProjectDetail.value
  const chapterCount = detail?.chapters?.length || 0
  if (chapterCount === 0) return '0'
  return (totalVersions.value / chapterCount).toFixed(1)
})
const progressPercent = computed(() => {
  const summary = selectedSummary.value
  if (!summary) return 0
  const total = summary.total_chapters || 0
  const done = summary.completed_chapters || 0
  if (!total) return 0
  return Math.round((done / total) * 100)
})
const progressCircle = computed(() => {
  const circumference = 2 * Math.PI * 24
  const filled = (progressPercent.value / 100) * circumference
  return `${filled} ${circumference}`
})
const featuredDesc = computed(() => {
  const detail = selectedProjectDetail.value
  if (detail?.blueprint?.full_synopsis) return detail.blueprint.full_synopsis.slice(0, 120) + '...'
  if (detail?.blueprint?.one_sentence_summary) return detail.blueprint.one_sentence_summary
  if (detail?.initial_prompt) return detail.initial_prompt.slice(0, 120) + '...'
  return '在被永恒阴雨笼罩的城市，你的故事正在展开...'
})
const recentChapters = computed(() => {
  const detail = selectedProjectDetail.value
  if (!detail?.chapters?.length) return []
  return detail.chapters
    .filter(ch => ch.word_count && ch.word_count > 0)
    .sort((a, b) => b.chapter_number - a.chapter_number)
    .slice(0, 3)
    .map(ch => ({
      number: ch.chapter_number,
      title: ch.title || `第${ch.chapter_number}章`,
      wordCount: ch.word_count || 0,
      status: ch.generation_status
    }))
})
const blueprint = computed(() => selectedProjectDetail.value?.blueprint || null)

const characterCount = computed(() => blueprint.value?.characters?.length || 0)
const characterNames = computed(() => {
  const chars = blueprint.value?.characters || []
  if (chars.length === 0) return '暂无角色'
  return chars.slice(0, 3).map((c: any) => c.name || c.identity || '').filter(Boolean).join('、') + (chars.length > 3 ? '...' : '')
})

const locationCount = computed(() => {
  const ws = blueprint.value?.world_setting || {}
  const locations = (ws as any).key_locations || (ws as any).locations || []
  return Array.isArray(locations) ? locations.length : 0
})
const locationNames = computed(() => {
  const ws = blueprint.value?.world_setting || {}
  const locations = (ws as any).key_locations || (ws as any).locations || []
  if (!Array.isArray(locations) || locations.length === 0) return '暂无地点设定'
  return locations.slice(0, 3).map((l: any) => typeof l === 'string' ? l : (l.name || l.location || '')).filter(Boolean).join('、') + (locations.length > 3 ? '...' : '')
})

const relationshipCount = computed(() => blueprint.value?.relationships?.length || 0)
const relationshipDesc = computed(() => {
  const rels = blueprint.value?.relationships || []
  if (rels.length === 0) return '暂无关系设定'
  return rels.slice(0, 2).map((r: any) => `${r.character_from}↔${r.character_to}`).join('、') + (rels.length > 2 ? '...' : '')
})

const chapterDotClass = (status: string) => {
  if (status === 'successful') return 'recent-dot--done'
  if (status === 'generating') return 'recent-dot--writing'
  return 'recent-dot--pending'
}
const loadProjectDetail = async (projectId: string) => {
  loadingDetail.value = true
  selectedProjectDetail.value = null
  try {
    selectedProjectDetail.value = await NovelAPI.getNovel(projectId)
  } catch (e) {
    console.error('加载项目详情失败', e)
  } finally {
    loadingDetail.value = false
  }
}
watch(selectedProjectId, (id) => {
  if (id) loadProjectDetail(id)
})

const selectProject = (project: NovelProjectSummary) => {
  if (selectedProjectId.value === project.id) return
  selectedProjectId.value = project.id
}

const goToInspiration = () => router.push('/inspiration')

const viewProjectDetail = (projectId: string) => router.push(`/detail/${projectId}`)

const enterProject = (project: NovelProjectSummary) => {
  if (project.title === '未命名灵感') {
    router.push(`/inspiration?project_id=${project.id}`)
  } else {
    router.push(`/novel/${project.id}`)
  }
}

const loadProjects = async () => {
  await novelStore.loadProjects()
  if (novelStore.projects.length > 0) {
    const firstId = novelStore.projects[0].id
    selectedProjectId.value = firstId
    await loadProjectDetail(firstId)
  }
}

const triggerImport = () => {
  if (isImporting.value) return
  fileInput.value?.click()
}

const handleFileImport = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  const file = target.files[0]
  if (!file.name.endsWith('.txt')) { alert('请上传 .txt 格式的文件'); return }
  isImporting.value = true
  try {
    const response = await NovelAPI.importNovel(file)
    await loadProjects()
    router.push(`/novel/${response.id}`)
  } catch (error: any) {
    console.error('导入失败:', error)
    alert(error.message || '导入失败，请重试')
  } finally {
    isImporting.value = false
    target.value = ''
  }
}

const handleDeleteProject = (projectId: string) => {
  const project = novelStore.projects.find(p => p.id === projectId)
  if (project) { projectToDelete.value = project; showDeleteDialog.value = true }
}

const cancelDelete = () => { showDeleteDialog.value = false; projectToDelete.value = null }

const confirmDelete = async () => {
  if (!projectToDelete.value) return
  isDeleting.value = true
  try {
    await novelStore.deleteProjects([projectToDelete.value.id])
    deleteMessage.value = { type: 'success', text: `项目 "${projectToDelete.value.title}" 已删除` }
    showDeleteDialog.value = false
    projectToDelete.value = null
    if (novelStore.projects.length > 0) {
      selectedProjectId.value = novelStore.projects[0].id
    } else {
      selectedProjectId.value = null
      selectedProjectDetail.value = null
    }
    setTimeout(() => { deleteMessage.value = null }, 3000)
  } catch {
    deleteMessage.value = { type: 'error', text: '删除失败，请重试' }
    setTimeout(() => { deleteMessage.value = null }, 3000)
  } finally {
    isDeleting.value = false
  }
}

onMounted(() => loadProjects())
</script>

<style scoped>
.workspace-root {
  min-height: calc(100vh - 56px);
  background: var(--ar-bg-base);
}

.workspace-layout {
  display: flex;
  min-height: calc(100vh - 56px);
}

/* Sidebar */
.workspace-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--ar-bg-surface);
  display: flex;
  flex-direction: column;
  padding: 20px 0;
  overflow-y: auto;
}

.sidebar-section-label {
  font-family: var(--ar-font-ui);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ar-text-muted);
  padding: 0 20px;
  margin-bottom: 8px;
}

.sidebar-novel-switcher {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  margin: 0 8px;
  border-radius: 4px;
  background: var(--ar-bg-elevated);
  font-size: 13px;
  font-weight: 500;
  color: var(--ar-text-primary);
  cursor: pointer;
  margin-bottom: 8px;
}

.sidebar-novels {
  flex: 0 0 auto;
  padding: 4px 8px;
  max-height: 200px;
  overflow-y: auto;
}

.sidebar-novel-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--ar-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.sidebar-novel-item:hover {
  background: rgba(255,255,255,0.04);
  color: var(--ar-text-primary);
}

.sidebar-novel-item--active {
  background: var(--ar-primary-muted);
  color: var(--ar-primary);
}

.sidebar-novel-icon { font-size: 14px; }
.sidebar-novel-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.sidebar-nav {
  margin-top: 20px;
  padding: 0 8px;
}

.sidebar-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 38px;
  padding: 0 12px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ar-text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.sidebar-nav-item:hover { background: rgba(255,255,255,0.04); color: var(--ar-text-primary); }

.sidebar-bottom {
  margin-top: auto;
  padding: 16px 8px 0;
}

.sidebar-cta {
  width: 100%;
  height: 40px;
  border: none;
  border-radius: 4px;
  background: var(--ar-primary);
  color: var(--ar-on-primary);
  font-family: var(--ar-font-ui);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.sidebar-cta:hover { box-shadow: 0 0 20px rgba(250,204,21,0.3); }

.sidebar-footer-links { margin-top: 12px; display: flex; flex-direction: column; gap: 2px; }

.sidebar-footer-link {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 32px;
  padding: 0 12px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ar-text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.sidebar-footer-link:hover { color: var(--ar-text-secondary); }

/* Main */
.workspace-main {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
  max-height: calc(100vh - 56px);
}

.welcome-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.welcome-section {
  flex: 1;
}

.welcome-title {
  font-family: var(--ar-font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--ar-text-primary);
  letter-spacing: -0.02em;
}

.welcome-subtitle {
  font-size: 14px;
  color: var(--ar-text-muted);
  margin-top: 4px;
}

/* Stats */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.stat-card {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 20px;
}

.stat-label {
  font-size: 12px;
  color: var(--ar-text-muted);
  margin-bottom: 8px;
  letter-spacing: 0.02em;
}

.stat-value {
  font-family: var(--ar-font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--ar-text-primary);
  line-height: 1;
}

.stat-value--primary { color: var(--ar-primary); }
.stat-value--green { color: var(--ar-secondary); }

.stat-trend {
  font-size: 11px;
  color: var(--ar-text-muted);
  margin-top: 8px;
}

.stat-trend-bar {
  height: 3px;
  background: rgba(74,222,128,0.15);
  border-radius: 2px;
  margin-top: 10px;
}

.stat-trend-bar-fill {
  height: 100%;
  background: var(--ar-secondary);
  border-radius: 2px;
}

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
}

.content-left { display: flex; flex-direction: column; gap: 24px; }
.content-right { display: flex; flex-direction: column; gap: 16px; }

/* Featured Card */
.featured-card {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 28px;
}

.featured-tags { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }

.featured-tag {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 2px;
  background: var(--ar-bg-highlight);
  color: var(--ar-text-primary);
}

.featured-tag--status {
  display: flex;
  align-items: center;
  gap: 5px;
  background: var(--ar-secondary-muted);
  color: var(--ar-secondary);
}

.featured-id {
  font-size: 11px;
  color: var(--ar-text-muted);
  margin-left: auto;
  font-family: var(--ar-font-mono);
}

.featured-title {
  font-family: var(--ar-font-manuscript);
  font-size: 26px;
  font-weight: 700;
  color: var(--ar-text-primary);
  margin-bottom: 12px;
}

.featured-desc {
  font-size: 14px;
  color: var(--ar-text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
}

.featured-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.featured-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-ring { position: relative; }

.progress-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--ar-font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--ar-primary);
}

.progress-label {
  font-size: 11px;
  color: var(--ar-text-muted);
  display: block;
}

.progress-detail {
  font-size: 13px;
  color: var(--ar-text-primary);
  font-weight: 500;
}

.continue-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 24px;
  border: none;
  border-radius: 4px;
  background: var(--ar-primary);
  color: var(--ar-on-primary);
  font-family: var(--ar-font-ui);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.continue-btn:hover { box-shadow: 0 0 24px rgba(250,204,21,0.35); }

/* Setting Library */
.setting-library {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 24px;
}

.setting-library-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }

.setting-library-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ar-text-primary);
}

.setting-categories { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }

.setting-cat {
  background: var(--ar-bg-elevated);
  border-radius: 4px;
  padding: 16px;
}

.setting-cat-count { font-size: 12px; color: var(--ar-text-muted); margin-top: 8px; display: block; }
.setting-cat-label { font-size: 14px; font-weight: 600; color: var(--ar-text-primary); margin-top: 4px; }
.setting-cat-desc { font-size: 12px; color: var(--ar-text-muted); margin-top: 2px; }

/* Projects Grid */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.create-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 140px;
  background: var(--ar-bg-surface);
  border-radius: 4px;
  border: 1px dashed rgba(77,70,50,0.2);
  cursor: pointer;
  transition: all 0.15s;
  font-size: 13px;
  font-weight: 500;
  color: var(--ar-text-secondary);
}

.create-card:hover { border-color: var(--ar-primary); color: var(--ar-primary); }

/* Right Panel Cards */
.ai-status-card {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 16px;
  border: 1px solid rgba(74,222,128,0.15);
  width: 300px;
  flex-shrink: 0;
}

.ai-status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-status-label {
  font-family: var(--ar-font-ui);
  font-size: 12px;
  font-weight: 600;
  color: var(--ar-secondary);
  letter-spacing: 0.04em;
}

.ai-status-latency {
  font-size: 11px;
  color: var(--ar-text-muted);
  margin-left: auto;
}

.ai-status-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--ar-text-muted);
}

.ai-status-tokens {
  font-family: var(--ar-font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--ar-text-primary);
}

.ai-status-bar {
  height: 4px;
  background: rgba(74,222,128,0.1);
  border-radius: 2px;
  margin-top: 6px;
}

.ai-status-bar-fill {
  height: 100%;
  background: var(--ar-secondary);
  border-radius: 2px;
}

/* Recent Chapters */
.recent-chapters {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 16px;
}

.recent-header { display: flex; justify-content: space-between; margin-bottom: 12px; }

.recent-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ar-text-primary);
}

.recent-view-all {
  font-size: 12px;
  color: var(--ar-primary);
  background: none;
  border: none;
  cursor: pointer;
}

.recent-list { display: flex; flex-direction: column; gap: 10px; }

.recent-item { display: flex; align-items: flex-start; gap: 10px; }

.recent-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.recent-dot--done { background: var(--ar-secondary); }
.recent-dot--writing { background: var(--ar-primary); animation: neon-pulse-primary-anim 2s ease-in-out infinite; }
.recent-dot--pending { background: var(--ar-text-muted); }

.recent-loading, .recent-empty {
  font-size: 12px;
  color: var(--ar-text-muted);
  padding: 8px 0;
  text-align: center;
}

.recent-item-title { font-size: 13px; font-weight: 500; color: var(--ar-text-primary); }
.recent-item-meta { font-size: 11px; color: var(--ar-text-muted); margin-top: 2px; }

/* AI Insight */
.ai-insight-card {
  background: linear-gradient(135deg, rgba(74,222,128,0.08), rgba(74,222,128,0.02));
  border-radius: 4px;
  padding: 16px;
  border: 1px solid rgba(74,222,128,0.1);
}

.ai-insight-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ar-primary);
  margin-bottom: 8px;
}

.ai-insight-text { font-size: 13px; color: var(--ar-text-secondary); line-height: 1.6; margin-bottom: 12px; }

.ai-insight-link {
  font-size: 13px;
  color: var(--ar-secondary);
  background: none;
  border: none;
  cursor: pointer;
  font-weight: 500;
}

@media (max-width: 1200px) {
  .content-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .welcome-row { flex-direction: column; }
  .ai-status-card { width: 100%; }
}

@media (max-width: 768px) {
  .workspace-sidebar { display: none; }
  .workspace-main { padding: 16px; }
  .stats-row { grid-template-columns: 1fr; }
  .setting-categories { grid-template-columns: 1fr; }
  .projects-grid { grid-template-columns: 1fr; }
}
</style>
