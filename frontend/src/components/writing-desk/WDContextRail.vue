<!-- AIMETA P=写作台本章上下文栏|R=人物_设定_伏笔引用_AI协作|NR=不含正文编辑|E=component:WDContextRail|X=ui|A=上下文组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="context-rail">
    <div class="context-head">
      <div><p>CHAPTER CONTEXT</p><h2>本章上下文</h2></div>
      <button type="button" title="预览生成上下文" @click="emit('previewContext')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 7v5l3 2M16 3h5v5"/></svg>
      </button>
    </div>

    <div class="context-scroll">
      <details open class="context-section">
        <summary><span><i class="section-dot character"></i>人物</span><b>{{ characters.length }}</b></summary>
        <div class="context-items">
          <button v-for="character in characters" :key="character.name" type="button" class="context-item">
            <span class="avatar">{{ character.name.slice(0, 1) }}</span>
            <span class="item-copy"><strong>{{ character.name }}</strong><small>{{ character.identity || character.relationship_to_protagonist || character.personality || '人物档案' }}</small></span>
            <span class="selected-mark">✓</span>
          </button>
          <p v-if="!characters.length" class="empty-copy">蓝图中还没有人物资料</p>
        </div>
      </details>

      <details open class="context-section">
        <summary><span><i class="section-dot setting"></i>设定</span><b>{{ settings.length }}</b></summary>
        <div class="context-items">
          <button v-for="setting in settings" :key="setting.key" type="button" class="context-item setting-item">
            <span class="setting-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3 3.5 7.5 12 12l8.5-4.5L12 3Z"/><path d="m3.5 12 8.5 4.5 8.5-4.5M3.5 16.5 12 21l8.5-4.5"/></svg>
            </span>
            <span class="item-copy"><strong>{{ setting.label }}</strong><small>{{ setting.summary }}</small></span>
            <span class="selected-mark">✓</span>
          </button>
          <p v-if="!settings.length" class="empty-copy">世界观设定将在这里集中引用</p>
        </div>
      </details>

      <details open class="context-section">
        <summary><span><i class="section-dot clue"></i>伏笔</span><b>{{ foreshadowings.length }}</b></summary>
        <div class="context-items">
          <button v-for="item in foreshadowings" :key="item.name || item.description" type="button" class="context-item clue-item">
            <span class="clue-line"></span>
            <span class="item-copy"><strong>{{ item.name || '未命名伏笔' }}</strong><small>{{ foreshadowingMeta(item) }}</small></span>
            <span class="selected-mark">✓</span>
          </button>
          <p v-if="!foreshadowings.length" class="empty-copy">本章暂时没有待处理伏笔</p>
        </div>
      </details>

      <section class="ai-card">
        <div class="ai-card-head">
          <span class="ai-orb"><i></i><b></b></span>
          <div><small>AI COPILOT</small><h3>AI 协作</h3></div>
        </div>
        <p>让 AI 基于当前章纲、人物关系和伏笔状态给出规划建议，不会直接改写正文。</p>
        <div class="suggestion-chips">
          <button type="button" @click="emit('openCodex')">检查人物动机</button>
          <button type="button" @click="emit('openCodex')">补强章节钩子</button>
        </div>
        <button type="button" class="ask-button" @click="emit('openCodex')">
          <span>与 AI 讨论本章</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>
        </button>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BlueprintForeshadowing, Character, NovelProject } from '@/api/novel'

const props = defineProps<{
  project: NovelProject
  selectedChapterNumber: number | null
}>()

const emit = defineEmits<{
  openCodex: []
  previewContext: []
}>()

const selectedOutline = computed(() =>
  props.project.blueprint?.chapter_outline?.find(
    (item) => item.chapter_number === props.selectedChapterNumber,
  ),
)

const characters = computed<Character[]>(() => {
  const all = props.project.blueprint?.characters || []
  const source = `${selectedOutline.value?.title || ''} ${selectedOutline.value?.summary || ''}`
  const matched = all.filter((character) => source.includes(character.name))
  return (matched.length ? matched : all).slice(0, 4)
})

const settings = computed(() => {
  const world = props.project.blueprint?.world_setting
  if (!world || typeof world !== 'object' || Array.isArray(world)) return []
  return Object.entries(world).slice(0, 4).map(([key, value]) => ({
    key,
    label: settingLabel(key),
    summary: summarize(value),
  }))
})

const foreshadowings = computed<BlueprintForeshadowing[]>(() =>
  (props.project.blueprint?.foreshadowings || [])
    .filter((item) => {
      const planted = item.planted_chapter || 1
      const target = item.target_chapter || Number.MAX_SAFE_INTEGER
      const current = props.selectedChapterNumber || 1
      return planted <= current && target >= current
    })
    .slice(0, 4),
)

function settingLabel(key: string): string {
  const labels: Record<string, string> = {
    power_system: '力量体系', geography: '地理与势力', factions: '阵营势力',
    social_structure: '社会结构', rules: '世界规则', core_rule: '核心规则',
    core_rules: '核心规则', key_location: '关键地点', key_locations: '关键地点',
    era: '时代背景',
  }
  return labels[key] || key.replace(/_/g, ' ')
}

function summarize(value: unknown): string {
  if (typeof value === 'string') return value.slice(0, 34)
  if (Array.isArray(value)) return value.slice(0, 3).map((item) => typeof item === 'string' ? item : '').filter(Boolean).join(' · ') || '查看设定详情'
  if (value && typeof value === 'object') {
    const first = Object.values(value).find((item) => typeof item === 'string')
    if (typeof first === 'string') return first.slice(0, 34)
  }
  return '查看设定详情'
}

function foreshadowingMeta(item: BlueprintForeshadowing): string {
  if (item.target_chapter) return `第 ${item.target_chapter} 章前回收 · ${item.tier || item.type || '普通'}`
  return item.description || item.reveal_method || '待安排回收时机'
}
</script>

<style scoped>
.context-rail { display: flex; width: 310px; min-width: 310px; height: 100%; flex-direction: column; overflow: hidden; border: 1px solid #242521; border-radius: 18px; background: rgba(17,18,16,.97); box-shadow: 0 24px 70px rgba(0,0,0,.2); }
.context-head { display: flex; align-items: center; justify-content: space-between; padding: 21px 18px 15px 21px; border-bottom: 1px solid #23241f; }
.context-head p { margin: 0 0 4px; color: #5f625b; font-size: 9px; font-weight: 800; letter-spacing: .16em; }
.context-head h2 { margin: 0; color: #f1f1eb; font-size: 16px; font-weight: 680; }
.context-head button { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid #2d2f29; border-radius: 8px; color: #84877f; background: #191a17; }
.context-head button:hover { color: #ffe500; }
.context-head svg { width: 15px; height: 15px; }
.context-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 10px 14px 17px; scrollbar-width: thin; scrollbar-color: #33352f transparent; }
.context-section { border-bottom: 1px solid #242520; }
.context-section summary { display: flex; align-items: center; justify-content: space-between; padding: 13px 4px 11px; color: #b7b9b1; font-size: 11px; font-weight: 650; cursor: pointer; list-style: none; }
.context-section summary::-webkit-details-marker { display: none; }
.context-section summary > span { display: flex; align-items: center; gap: 8px; }
.context-section summary b { display: grid; min-width: 19px; height: 19px; place-items: center; border-radius: 6px; color: #6d7068; font-size: 9px; background: #20211d; }
.section-dot { width: 6px; height: 6px; border-radius: 50%; background: #c6b919; box-shadow: 0 0 10px rgba(255,229,0,.2); }
.section-dot.setting { background: #668aa5; box-shadow: none; }
.section-dot.clue { background: #9976a7; box-shadow: none; }
.context-items { padding: 0 0 12px; }
.context-item { display: grid; width: 100%; grid-template-columns: 30px minmax(0,1fr) 16px; align-items: center; gap: 9px; margin-bottom: 5px; padding: 8px 8px; border: 1px solid transparent; border-radius: 8px; text-align: left; background: #151613; transition: .16s ease; }
.context-item:hover { border-color: #33352f; background: #1a1b18; }
.avatar { display: grid; width: 28px; height: 28px; place-items: center; border: 1px solid #47473a; border-radius: 8px; color: #d3c51d; font-size: 10px; font-weight: 750; background: #24241d; }
.setting-icon { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 8px; color: #7e9db4; background: #1c2327; }
.setting-icon svg { width: 15px; height: 15px; }
.item-copy { display: flex; min-width: 0; flex-direction: column; }
.item-copy strong { overflow: hidden; color: #bfc1b9; font-size: 10px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.item-copy small { margin-top: 3px; overflow: hidden; color: #666961; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }
.selected-mark { display: grid; width: 15px; height: 15px; place-items: center; border-radius: 4px; color: #0d0e0c; font-size: 8px; font-weight: 850; background: #bdb21c; }
.clue-line { width: 22px; height: 2px; border-radius: 9px; background: linear-gradient(90deg,#805d8c,#c2a3cc); }
.empty-copy { margin: 3px 7px 8px; color: #5f625a; font-size: 9px; }
.ai-card { margin-top: 15px; padding: 15px; border: 1px solid #3a3826; border-radius: 12px; background: linear-gradient(145deg,rgba(255,229,0,.045),rgba(21,22,18,.8)); }
.ai-card-head { display: flex; align-items: center; gap: 10px; }
.ai-orb { position: relative; display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid #5c5725; border-radius: 10px; background: #222219; }
.ai-orb i { width: 8px; height: 8px; border-radius: 50%; background: #ffe500; box-shadow: 0 0 12px rgba(255,229,0,.55); }
.ai-orb b { position: absolute; width: 20px; height: 20px; border: 1px solid rgba(255,229,0,.22); border-radius: 50%; }
.ai-card small { color: #77712c; font-size: 7px; font-weight: 850; letter-spacing: .13em; }
.ai-card h3 { margin: 1px 0 0; color: #e0e1d9; font-size: 12px; }
.ai-card > p { margin: 11px 0; color: #777a72; font-size: 9px; line-height: 15px; }
.suggestion-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.suggestion-chips button { padding: 5px 7px; border: 1px solid #34352d; border-radius: 6px; color: #8c8f87; font-size: 8px; background: #191a17; }
.ask-button { display: flex; width: 100%; height: 34px; align-items: center; justify-content: space-between; margin-top: 11px; padding: 0 11px; border: 1px solid #625c24; border-radius: 8px; color: #dfd01d; font-size: 9px; font-weight: 700; background: rgba(255,229,0,.055); }
.ask-button:hover { border-color: #92861d; background: rgba(255,229,0,.09); }
.ask-button svg { width: 14px; height: 14px; }
@media (max-width: 1500px) { .context-rail { width: 278px; min-width: 278px; } }
</style>
