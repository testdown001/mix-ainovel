<!-- AIMETA P=写作台头部_创作工作流导航|R=项目元信息_阶段切换_预览_设置_更多操作|NR=不含内容区域|E=component:WDHeader|X=ui|A=头部组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <header class="desk-header">
    <div class="header-main">
      <div class="header-left">
        <button type="button" class="icon-button back-button" aria-label="返回工作区" @click="emit('goBack')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m15 18-6-6 6-6" /></svg>
        </button>
        <div class="project-copy">
          <div class="project-title-line">
            <h1>{{ project?.title || '加载中…' }}</h1>
            <span class="project-meta">{{ projectMeta }}</span>
          </div>
          <div class="save-state">
            <span class="save-dot"></span>
            <span>{{ autosaveText || '已自动保存' }}</span>
          </div>
        </div>
      </div>

      <div class="header-actions">
        <button type="button" class="header-action preview-action" @click="emit('viewProjectDetail')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2.7 12s3.4-5.3 9.3-5.3 9.3 5.3 9.3 5.3-3.4 5.3-9.3 5.3S2.7 12 2.7 12Z"/><circle cx="12" cy="12" r="2.5"/></svg>
          <span>预览</span>
        </button>

        <div class="more-wrap">
          <button type="button" class="header-action" :class="{ active: moreOpen }" @click="moreOpen = !moreOpen">
            <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
            <span>更多</span>
          </button>
          <div v-if="moreOpen" class="more-menu">
            <button type="button" @click="openExport"><span>导出全书</span><small>MD / TXT / DOCX</small></button>
            <button type="button" @click="openPrecheck"><span>投稿预检</span><small>敏感词扫描</small></button>
            <button type="button" @click="emit('openTools'); moreOpen = false"><span>创作工具</span><small>批量、预设与诊断</small></button>
            <i></i>
            <button type="button" class="logout-item" @click="handleLogout"><span>退出登录</span></button>
          </div>
          <div v-if="exportOpen" class="export-menu">
            <button type="button" :disabled="exporting" @click="exportBook('markdown')">导出 Markdown</button>
            <button type="button" :disabled="exporting" @click="exportBook('txt')">导出 TXT</button>
            <button type="button" :disabled="exporting" @click="exportBook('docx')">导出 DOCX</button>
          </div>
        </div>

        <button type="button" class="settings-action" :class="{ active: modelSettingsOpen }" @click="emit('toggleModelSettings')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 8.94 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.57 15 1.7 1.7 0 0 0 3 14H3v-4h.08A1.7 1.7 0 0 0 4.6 8.94a1.7 1.7 0 0 0-.34-1.88L4.2 7l2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.57 1.7 1.7 0 0 0 10 3V3h4v.08A1.7 1.7 0 0 0 15.06 4.6a1.7 1.7 0 0 0 1.88-.34L17 4.2 19.83 7l-.06.06A1.7 1.7 0 0 0 19.43 9 1.7 1.7 0 0 0 21 10h.08v4H21a1.7 1.7 0 0 0-1.6 1Z"/></svg>
          <span>模型与设置</span>
        </button>

        <button type="button" class="icon-button mobile-menu" aria-label="打开章节与工具" @click="emit('openTools')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
        </button>
      </div>
    </div>

    <nav class="stage-nav" aria-label="章节创作流程">
      <template v-for="(stage, index) in stages" :key="stage.id">
        <button
          type="button"
          :class="{ active: activeStage === stage.id, done: activeStage > stage.id }"
          @click="emit('selectStage', stage.id)"
        >
          <span class="stage-number">{{ String(stage.id).padStart(2, '0') }}</span>
          <strong>{{ stage.label }}</strong>
          <span v-if="activeStage > stage.id" class="stage-check">✓</span>
        </button>
        <i v-if="index < stages.length - 1" :class="{ done: activeStage > stage.id }"></i>
      </template>
    </nav>
  </header>

  <Teleport to="body">
    <div v-if="precheckOpen" class="modal-backdrop" @click.self="precheckOpen = false">
      <div class="precheck-modal">
        <div class="modal-heading"><div><small>CONSISTENCY CHECK</small><h3>投稿预检</h3></div><button type="button" @click="precheckOpen = false">×</button></div>
        <p>对照平台词表扫描已完稿正文。命中只提示，不会阻止导出或继续写作。</p>
        <select v-model="precheckPlatform">
          <option value="qidian">起点</option><option value="fanqie">番茄</option><option value="jjwxc">晋江</option>
        </select>
        <div class="modal-actions">
          <button type="button" class="run-check" :disabled="prechecking" @click="runPrecheck">{{ prechecking ? '扫描中…' : '开始预检' }}</button>
          <button type="button" @click="precheckOpen = false">关闭</button>
        </div>
        <p v-if="precheckResult" class="check-result">{{ precheckResult.message }}</p>
        <div v-if="precheckResult?.hits?.length" class="check-hits">
          <div v-for="(hit, index) in precheckResult.hits" :key="index"><strong>{{ hit.term }}</strong><span>…{{ hit.snippet }}…</span></div>
        </div>
        <button v-if="precheckResult" type="button" class="download-report" @click="downloadPrecheckReport">下载预检报告</button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { NovelAPI, type CompliancePrecheckResult, type NovelProject } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { AUTHORING_STAGES } from '@/utils/writingWorkflow'

interface Props {
  project: NovelProject | null
  progress: number
  completedChapters: number
  totalChapters: number
  activeStage: number
  wordCount: number
  autosaveText?: string
  modelSettingsOpen?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  goBack: []
  viewProjectDetail: []
  openTools: []
  toggleModelSettings: []
  selectStage: [stage: number]
}>()

const router = useRouter()
const authStore = useAuthStore()
const moreOpen = ref(false)
const exportOpen = ref(false)
const exporting = ref(false)
const precheckOpen = ref(false)
const prechecking = ref(false)
const precheckPlatform = ref<'qidian' | 'fanqie' | 'jjwxc'>('qidian')
const precheckResult = ref<CompliancePrecheckResult | null>(null)

const stages = AUTHORING_STAGES

const projectMeta = computed(() => {
  const genre = props.project?.blueprint?.genre || '类型待定'
  const words = props.wordCount >= 10000
    ? `${(props.wordCount / 10000).toFixed(1)}万字`
    : `${props.wordCount}字`
  const state = props.project?.is_completed ? '已完结' : '连载中'
  return `${genre} · ${words} · ${state}`
})

function openExport() {
  moreOpen.value = false
  exportOpen.value = !exportOpen.value
}

function openPrecheck() {
  moreOpen.value = false
  precheckOpen.value = true
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

async function exportBook(format: 'txt' | 'markdown' | 'docx') {
  if (!props.project?.id) return
  exporting.value = true
  exportOpen.value = false
  try {
    await NovelAPI.exportManuscript(props.project.id, format)
    globalAlert.showSuccess('已开始下载已完稿章节；服务器不会保留导出文件。', '导出全书')
  } catch (error) {
    globalAlert.showError(error instanceof Error ? error.message : '导出失败', '导出全书')
  } finally {
    exporting.value = false
  }
}

async function runPrecheck() {
  if (!props.project?.id) return
  prechecking.value = true
  try {
    precheckResult.value = await NovelAPI.compliancePrecheck(props.project.id, precheckPlatform.value)
  } catch (error) {
    globalAlert.showError(error instanceof Error ? error.message : '预检失败', '投稿预检')
  } finally {
    prechecking.value = false
  }
}

function downloadPrecheckReport() {
  const result = precheckResult.value
  if (!result || !props.project?.title) return
  const lines = [
    `${props.project.title} · 投稿敏感词预检报告`,
    `平台：${precheckPlatform.value}`,
    `命中：${result.hit_count} 处`,
    '',
    result.message,
    '',
    ...result.hits.map((hit, index) => `${index + 1}. ${hit.term}\n   片段：${hit.snippet}`),
  ]
  const blob = new Blob([`${lines.join('\n')}\n`], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${props.project.title.slice(0, 80)}-投稿预检报告.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.desk-header { position: relative; z-index: 35; flex-shrink: 0; border-bottom: 1px solid #262720; background: rgba(15,16,14,.96); backdrop-filter: blur(18px); }
.header-main { display: flex; height: 62px; align-items: center; justify-content: space-between; gap: 20px; padding: 0 24px; }
.header-left, .header-actions, .project-title-line, .save-state { display: flex; align-items: center; }
.header-left { min-width: 0; gap: 12px; }
.icon-button { display: grid; width: 33px; height: 33px; flex-shrink: 0; place-items: center; border: 1px solid transparent; border-radius: 8px; color: #80837b; background: transparent; }
.icon-button:hover { border-color: #31332d; color: #f1f1ea; background: #1a1b18; }
.icon-button svg { width: 19px; height: 19px; }
.project-copy { min-width: 0; }
.project-title-line { min-width: 0; gap: 10px; }
.project-title-line h1 { max-width: 440px; margin: 0; overflow: hidden; color: #f7f7f1; font-size: 16px; font-weight: 680; letter-spacing: -.015em; text-overflow: ellipsis; white-space: nowrap; }
.project-meta { padding: 4px 9px; border: 1px solid #2e302a; border-radius: 99px; color: #74776f; font-size: 9px; white-space: nowrap; background: #191a17; }
.save-state { gap: 5px; margin-top: 4px; color: #5e615a; font-size: 8px; }
.save-dot { width: 5px; height: 5px; border-radius: 50%; background: #43d486; box-shadow: 0 0 9px rgba(67,212,134,.36); }
.header-actions { flex-shrink: 0; gap: 6px; }
.header-action, .settings-action { display: inline-flex; height: 34px; align-items: center; gap: 7px; padding: 0 11px; border: 1px solid transparent; border-radius: 8px; color: #84877f; font-size: 10px; background: transparent; transition: .16s ease; }
.header-action:hover, .header-action.active { border-color: #30322c; color: #e5e6de; background: #1a1b18; }
.header-action svg, .settings-action svg { width: 15px; height: 15px; }
.settings-action { border-color: #343630; color: #c6c8bf; background: #1b1c19; }
.settings-action:hover, .settings-action.active { border-color: #665f20; color: #f2df26; background: #232319; }
.more-wrap { position: relative; }
.more-menu, .export-menu { position: absolute; z-index: 60; top: 40px; right: 0; width: 210px; padding: 6px; border: 1px solid #30322c; border-radius: 10px; background: #191a17; box-shadow: 0 18px 50px rgba(0,0,0,.45); }
.more-menu button { display: flex; width: 100%; align-items: center; justify-content: space-between; padding: 9px 10px; border: 0; border-radius: 7px; color: #c4c6bd; font-size: 10px; background: transparent; }
.more-menu button:hover, .export-menu button:hover { background: #242520; }
.more-menu small { color: #62655e; font-size: 8px; }
.more-menu i { display: block; height: 1px; margin: 4px; background: #2b2d27; }
.more-menu .logout-item { color: #b67b74; }
.export-menu { width: 126px; }
.export-menu button { width: 100%; padding: 9px; border: 0; border-radius: 6px; color: #c4c6bd; font-size: 10px; text-align: left; background: transparent; }
.mobile-menu { display: none; }
.stage-nav { display: flex; height: 54px; align-items: center; justify-content: center; }
.stage-nav > button { position: relative; display: flex; height: 32px; align-items: center; gap: 8px; padding: 0 12px; border: 0; border-radius: 7px; color: #656860; font-size: 10px; background: transparent; transition: .16s ease; }
.stage-nav > button:hover { color: #b5b7af; background: #191a17; }
.stage-nav > button.active { color: #0c0d0b; background: #ffe500; box-shadow: 0 7px 24px rgba(255,229,0,.1); }
.stage-nav > button.done { color: #91948b; }
.stage-number { font-size: 8px; font-weight: 850; letter-spacing: .06em; }
.stage-nav strong { font-weight: 680; }
.stage-check { color: #3acb7f; font-size: 9px; }
.stage-nav > button.active .stage-check { color: #0c0d0b; }
.stage-nav > i { width: 64px; height: 1px; margin: 0 5px; background: #30322b; }
.stage-nav > i.done { background: #545127; }
.modal-backdrop { position: fixed; z-index: 100; inset: 0; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(0,0,0,.64); backdrop-filter: blur(5px); }
.precheck-modal { width: 440px; max-width: 100%; padding: 20px; border: 1px solid #32342e; border-radius: 14px; color: #bfc1b9; background: #151613; box-shadow: 0 26px 80px rgba(0,0,0,.5); }
.modal-heading { display: flex; align-items: flex-start; justify-content: space-between; }
.modal-heading small { color: #70691e; font-size: 8px; font-weight: 850; letter-spacing: .13em; }
.modal-heading h3 { margin: 3px 0 0; color: #f1f1ea; font-size: 16px; }
.modal-heading button { border: 0; color: #74776f; font-size: 22px; background: transparent; }
.precheck-modal > p { color: #777a72; font-size: 10px; line-height: 17px; }
.precheck-modal select { width: 100%; padding: 9px 10px; border: 1px solid #343630; border-radius: 8px; color: #ddd; background: #10110f; }
.modal-actions { display: flex; gap: 8px; margin-top: 12px; }
.modal-actions button { padding: 8px 12px; border: 1px solid #343630; border-radius: 7px; color: #999c94; font-size: 10px; background: #1a1b18; }
.modal-actions .run-check { border-color: #ffe500; color: #10110f; font-weight: 750; background: #ffe500; }
.check-hits { max-height: 180px; overflow-y: auto; }
.check-hits div { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; padding: 8px; border-radius: 7px; font-size: 9px; background: #1c1d1a; }
.check-hits strong { color: #d4c51e; }.check-hits span { color: #7c7f77; }
.download-report { width: 100%; margin-top: 12px; padding: 8px 10px; border: 1px solid #5a541d; border-radius: 7px; color: #e7d722; font-size: 10px; font-weight: 700; background: #1c1c14; }
@media (max-width: 900px) { .project-meta, .preview-action span, .header-action span, .settings-action span { display: none; } .header-main { padding: 0 12px; } .stage-nav > i { width: 20px; } .stage-nav > button { padding: 0 8px; } }
@media (max-width: 640px) { .header-actions > .more-wrap, .header-actions > .settings-action { display: none; } .mobile-menu { display: grid; } .project-title-line h1 { max-width: 245px; font-size: 14px; } .stage-nav { height: 47px; overflow-x: auto; justify-content: flex-start; padding: 0 12px; } .stage-nav > button { flex-shrink: 0; } }
</style>
