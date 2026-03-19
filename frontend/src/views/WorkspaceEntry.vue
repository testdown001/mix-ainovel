<!-- AIMETA P=工作区入口_应用主入口|R=入口导航|NR=不含具体功能|E=route:/#component:WorkspaceEntry|X=ui|A=入口页|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="workspace-entry">
    <!-- Update Log Modal -->
    <div v-if="showModal" class="ws-overlay" @click.self="closeModal">
      <div class="ws-dialog w-full max-w-4xl mx-4 max-h-[90vh] flex flex-col">
        <!-- Header -->
        <div class="ws-dialog-header">
          <h1 class="ar-h2 text-center" style="color: var(--ar-text-primary);">更新日志</h1>
        </div>
        
        <!-- Community Section -->
        <div v-if="communityLog" class="px-6 pt-6">
          <div class="ws-community-card">
            <div class="prose max-w-none prose-sm" style="color: var(--ar-primary);" v-html="renderMarkdown(communityLog.content)"></div>
          </div>
        </div>

        <!-- Timeline Content -->
        <div class="px-6 py-6 overflow-y-auto flex-1">
          <div class="flow-root">
            <ul role="list" class="-mb-8">
              <li v-for="(log, index) in filteredUpdateLogs" :key="log.id">
                <div class="relative pb-8">
                  <!-- Connector Line -->
                  <span 
                    v-if="index < filteredUpdateLogs.length - 1" 
                    class="absolute left-2.5 top-4 -ml-px h-full w-0.5"
                    style="background: linear-gradient(180deg, var(--ar-primary-muted), transparent);"
                    aria-hidden="true"
                  ></span>
                  <div class="relative flex items-start space-x-4">
                    <!-- Timeline Dot -->
                    <div class="ws-timeline-dot"></div>
                    <!-- Card Content -->
                    <div class="min-w-0 flex-1">
                      <div class="ws-timeline-card">
                        <time class="ar-label-sm" style="color: var(--ar-text-muted);">
                          {{ new Date(log.created_at).toLocaleDateString() }}
                        </time>
                        <div class="mt-3 prose max-w-none prose-sm" style="color: var(--ar-text-primary);" v-html="renderMarkdown(log.content)"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>
        
        <!-- Footer Actions -->
        <div class="ws-dialog-actions">
          <button @click="hideModalToday" class="md-btn md-btn-text md-ripple">
            今日不再显示
          </button>
          <button @click="closeModal" class="md-btn md-btn-filled md-ripple">
            关闭
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="w-full max-w-4xl mx-auto">
      <div class="text-center p-8 fade-in">
        <!-- Title -->
        <h1 class="ws-title">
          拯救小说家：创作中心
        </h1>
        <p class="ar-body-lg mb-12" style="color: var(--ar-text-secondary);">
          从一个新灵感开始，或继续打磨你的世界。
        </p>

        <!-- Mode Selection Cards -->
        <div class="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto stagger-reveal">
          <!-- Inspiration Mode Card -->
          <div
            @click="goToInspiration"
            class="ws-mode-card group"
          >
            <div class="ws-mode-icon" style="background-color: var(--ar-primary-muted);">
              <svg class="w-8 h-8" style="color: var(--ar-primary);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h2 class="ar-h3 mb-2" style="color: var(--ar-primary);">灵感模式</h2>
            <p class="ar-body" style="color: var(--ar-text-secondary);">
              没有头绪？让AI通过对话式引导，帮你构建故事的雏形。
            </p>
          </div>

          <!-- Novel Workspace Card -->
          <div
            @click="goToWorkspace"
            class="ws-mode-card group"
          >
            <div class="ws-mode-icon" style="background-color: var(--ar-secondary-muted);">
              <svg class="w-8 h-8" style="color: var(--ar-secondary);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h2 class="ar-h3 mb-2" style="color: var(--ar-secondary);">小说工作台</h2>
            <p class="ar-body" style="color: var(--ar-text-secondary);">
              查看、编辑和管理你所有的小说项目工程。
            </p>
          </div>
        </div>

        <div class="flex justify-center gap-2 mt-12">
          <div class="ws-accent-bar w-16"></div>
          <div class="ws-accent-bar ws-accent-bar--dim w-8"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { marked } from 'marked'
import { useRouter } from 'vue-router'
import { getLatestUpdates } from '../api/updates'
import type { UpdateLog } from '../api/updates'

marked.setOptions({
  gfm: true,
  breaks: true
})

const renderMarkdown = (md: string) => marked.parse(md)

const router = useRouter()

const showModal = ref(false)
const updateLogs = ref<UpdateLog[]>([])

// 查找包含"交流群"的日志
const communityLog = computed(() => {
  return updateLogs.value.find(log => /交流群/.test(log.content))
})

// 过滤掉包含"交流群"的日志，用于时间线显示
const filteredUpdateLogs = computed(() => {
  if (!communityLog.value) {
    return updateLogs.value
  }
  return updateLogs.value.filter(log => log.id !== communityLog.value!.id)
})

onMounted(async () => {
  const hideUntil = localStorage.getItem('hideAnnouncement')
  if (hideUntil !== new Date().toDateString()) {
    try {
      updateLogs.value = await getLatestUpdates()
      if (updateLogs.value.length > 0) {
        showModal.value = true
      }
    } catch (error) {
      console.error('Failed to fetch update logs:', error)
    }
  }
})

const closeModal = () => {
  showModal.value = false
}

const hideModalToday = () => {
  localStorage.setItem('hideAnnouncement', new Date().toDateString())
  closeModal()
}

const goToInspiration = () => {
  router.push('/inspiration')
}

const goToWorkspace = () => {
  router.push('/workspace')
}
</script>

<style scoped>
.workspace-entry {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 64px);
  padding: 16px;
  position: relative;
  background-color: var(--ar-bg-base);
  background-image:
    radial-gradient(ellipse at 20% 50%, rgba(250, 204, 21, 0.03) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 50%, rgba(74, 222, 128, 0.02) 0%, transparent 50%);
}

/* Modal overlay */
.ws-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.ws-dialog {
  background-color: var(--ar-bg-elevated);
  border-radius: var(--ar-radius-sm);
  box-shadow: var(--ar-elevation-glow);
  border: 1px solid var(--ar-border);
}

.ws-dialog-header {
  padding: 24px 24px 16px;
  border-bottom: 1px solid var(--ar-border);
}

.ws-dialog-actions {
  padding: 16px 24px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--ar-border);
  background-color: var(--ar-bg-surface);
}

.ws-community-card {
  padding: 16px;
  border-radius: var(--ar-radius-sm);
  background-color: var(--ar-primary-muted);
  border: 1px solid rgba(250, 204, 21, 0.1);
}

.ws-timeline-dot {
  width: 20px;
  height: 20px;
  border-radius: var(--ar-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
  flex-shrink: 0;
  background-color: var(--ar-primary);
  box-shadow: 0 0 12px rgba(250, 204, 21, 0.4);
}

.ws-timeline-card {
  padding: 16px;
  background-color: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  transition: all var(--ar-duration-medium) var(--ar-easing-standard);
}

.ws-timeline-card:hover {
  background-color: var(--ar-bg-elevated);
  box-shadow: var(--ar-elevation-glow);
}

/* Main title */
.ws-title {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-h1);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.01em;
  color: var(--ar-text-primary);
  margin-bottom: 16px;
}

/* Mode selection cards */
.ws-mode-card {
  padding: 32px;
  cursor: pointer;
  background-color: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  box-shadow: var(--ar-elevation-1);
  transition: all var(--ar-duration-medium) var(--ar-easing-standard);
}

.ws-mode-card:hover {
  background-color: var(--ar-bg-elevated);
  box-shadow: var(--ar-elevation-glow);
  border-color: rgba(77, 70, 50, 0.3);
  transform: translateY(-2px);
}

.ws-mode-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: var(--ar-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Decorative accent bars */
.ws-accent-bar {
  height: 3px;
  border-radius: 1px;
  background: linear-gradient(90deg, var(--ar-primary), var(--ar-primary-dim));
}

.ws-accent-bar--dim {
  opacity: 0.4;
}
</style>
