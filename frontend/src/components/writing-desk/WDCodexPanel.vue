<!-- AIMETA P=世界观设定典面板|R=角色_世界观_关系_伏笔|NR=不含编辑功能|E=component:WDCodexPanel|X=ui|A=抽屉面板|D=vue|S=dom|RD=./README.ai -->
<template>
  <Teleport to="body">
    <!-- 遮罩层 -->
    <Transition name="codex-overlay">
      <div
        v-if="visible"
        class="fixed inset-0 z-40"
        style="background-color: rgba(0, 0, 0, 0.32);"
        @click="$emit('update:visible', false)"
      />
    </Transition>

    <!-- 侧滑面板 -->
    <Transition name="codex-panel">
      <div
        v-if="visible"
        class="fixed top-0 right-0 h-full w-96 z-50 flex flex-col overflow-hidden"
        style="background-color: var(--md-surface); box-shadow: var(--md-elevation-3);"
      >
        <!-- 顶部 -->
        <div class="flex items-center justify-between px-5 py-4 flex-shrink-0" style="border-bottom: 1px solid var(--md-outline-variant);">
          <h2 class="md-title-large font-semibold" style="color: var(--md-on-surface);">世界观设定典</h2>
          <button
            @click="$emit('update:visible', false)"
            class="md-icon-btn md-ripple"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>

        <!-- Tab 切换栏 -->
        <div class="flex flex-shrink-0 px-2" style="border-bottom: 1px solid var(--md-outline-variant);">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            class="flex-1 py-3 text-center md-label-large transition-colors relative"
            :style="{
              color: activeTab === tab.key ? 'var(--md-primary)' : 'var(--md-on-surface-variant)',
            }"
          >
            {{ tab.label }}
            <span
              v-if="activeTab === tab.key"
              class="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full"
              style="background-color: var(--md-primary);"
            />
          </button>
        </div>

        <!-- Tab 内容 -->
        <div class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          <!-- 角色 Tab -->
          <template v-if="activeTab === 'characters'">
            <div v-if="!sortedCharacters.length" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无角色数据
            </div>
            <div
              v-for="char in sortedCharacters"
              :key="char.name"
              class="md-card md-card-outlined p-3 transition-all"
              :style="{
                borderRadius: 'var(--md-radius-lg)',
                borderColor: isRelevant(char.name) ? 'var(--md-primary)' : undefined,
                backgroundColor: isRelevant(char.name) ? 'var(--md-primary-container)' : undefined,
              }"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="md-title-small font-semibold" :style="{ color: isRelevant(char.name) ? 'var(--md-on-primary-container)' : 'var(--md-on-surface)' }">
                  {{ char.name }}
                </span>
                <span v-if="isRelevant(char.name)" class="md-chip m3-chip-success !text-[10px] !px-1.5 !py-0">本章相关</span>
                <span v-if="char.identity" class="md-body-small md-on-surface-variant">{{ char.identity }}</span>
              </div>
              <p class="md-body-small md-on-surface-variant line-clamp-2">{{ char.description }}</p>
              <details v-if="char.personality || char.goals || char.abilities" class="mt-1.5">
                <summary class="md-label-small cursor-pointer" style="color: var(--md-primary);">展开详情</summary>
                <div class="mt-1.5 space-y-1 md-body-small md-on-surface-variant">
                  <p v-if="char.personality"><span class="font-medium">性格：</span>{{ char.personality }}</p>
                  <p v-if="char.goals"><span class="font-medium">目标：</span>{{ char.goals }}</p>
                  <p v-if="char.abilities"><span class="font-medium">能力：</span>{{ char.abilities }}</p>
                </div>
              </details>
            </div>
          </template>

          <!-- 世界观 Tab -->
          <template v-if="activeTab === 'world'">
            <div v-if="!hasWorldData" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无世界观数据
            </div>
            <template v-else>
              <!-- 核心规则 -->
              <div v-if="worldSetting?.core_rules" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
                <h4 class="md-title-small font-semibold mb-2" style="color: var(--md-on-surface);">核心规则</h4>
                <p class="md-body-small md-on-surface-variant whitespace-pre-line">{{ worldSetting.core_rules }}</p>
              </div>
              <!-- 关键地点 -->
              <div v-if="worldSetting?.key_locations?.length" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
                <h4 class="md-title-small font-semibold mb-2" style="color: var(--md-on-surface);">关键地点</h4>
                <div v-for="loc in worldSetting.key_locations" :key="loc.title" class="mb-2 last:mb-0">
                  <span class="md-label-medium font-medium" style="color: var(--md-primary);">{{ loc.title }}</span>
                  <p class="md-body-small md-on-surface-variant">{{ loc.description }}</p>
                </div>
              </div>
              <!-- 势力 -->
              <div v-if="worldSetting?.factions?.length" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
                <h4 class="md-title-small font-semibold mb-2" style="color: var(--md-on-surface);">势力阵营</h4>
                <div v-for="fac in worldSetting.factions" :key="fac.title" class="mb-2 last:mb-0">
                  <span class="md-label-medium font-medium" style="color: var(--md-primary);">{{ fac.title }}</span>
                  <p class="md-body-small md-on-surface-variant">{{ fac.description }}</p>
                </div>
              </div>
            </template>
          </template>

          <!-- 关系 Tab -->
          <template v-if="activeTab === 'relations'">
            <div v-if="!relationships?.length" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无关系数据
            </div>
            <div
              v-for="(rel, i) in relationships"
              :key="i"
              class="md-card md-card-outlined p-3"
              style="border-radius: var(--md-radius-lg);"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="md-label-large font-semibold" style="color: var(--md-on-surface);">{{ rel.from || rel.character_a || '?' }}</span>
                <svg class="w-4 h-4 shrink-0" style="color: var(--md-primary);" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
                <span class="md-label-large font-semibold" style="color: var(--md-on-surface);">{{ rel.to || rel.character_b || '?' }}</span>
              </div>
              <p class="md-body-small md-on-surface-variant">{{ rel.description || rel.relationship || '' }}</p>
            </div>
          </template>

          <!-- 伏笔 Tab -->
          <template v-if="activeTab === 'foreshadowing'">
            <div v-if="!allForeshadowing.length" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无伏笔数据
            </div>
            <div
              v-for="(fs, i) in allForeshadowing"
              :key="i"
              class="md-card md-card-outlined p-3"
              style="border-radius: var(--md-radius-lg);"
            >
              <div class="flex items-center gap-2 mb-1">
                <span
                  class="md-chip !text-[10px] !px-1.5 !py-0"
                  :class="fs.type === 'hook' ? 'm3-chip-success' : 'm3-chip-warning'"
                >
                  {{ fs.type === 'hook' ? '埋设' : '回收' }}
                </span>
                <span class="md-label-small md-on-surface-variant">第{{ fs.chapter }}章</span>
              </div>
              <p class="md-body-small md-on-surface">{{ fs.text }}</p>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Blueprint, ChapterOutline, Character } from '@/api/novel'

interface Props {
  visible: boolean
  blueprint: Blueprint | null | undefined
  selectedChapterNumber: number | null
  outlines: ChapterOutline[]
}

const props = defineProps<Props>()
defineEmits(['update:visible'])

const tabs = [
  { key: 'characters', label: '角色' },
  { key: 'world', label: '世界观' },
  { key: 'relations', label: '关系' },
  { key: 'foreshadowing', label: '伏笔' },
] as const

type TabKey = typeof tabs[number]['key']

const activeTab = ref<TabKey>('characters')

// 当前章节大纲文本，用于高亮匹配
const currentSummary = computed(() => {
  const outline = props.outlines?.find(o => o.chapter_number === props.selectedChapterNumber)
  return (outline?.summary || '') + ' ' + (outline?.title || '')
})

const isRelevant = (name: string) => name && currentSummary.value.includes(name)

// 角色排序：相关角色置顶
const sortedCharacters = computed<Character[]>(() => {
  const chars = props.blueprint?.characters || []
  return [...chars].sort((a, b) => {
    const aRel = isRelevant(a.name) ? 1 : 0
    const bRel = isRelevant(b.name) ? 1 : 0
    return bRel - aRel
  })
})

// 世界观
const worldSetting = computed(() => props.blueprint?.world_setting)
const hasWorldData = computed(() => {
  const ws = worldSetting.value
  if (!ws) return false
  return ws.core_rules || ws.key_locations?.length || ws.factions?.length
})

// 关系
const relationships = computed(() => props.blueprint?.relationships || [])

// 伏笔：从所有 outlines 的 prediction 中收集
interface ForeshadowingItem {
  chapter: number
  type: 'hook' | 'target'
  text: string
}

const allForeshadowing = computed<ForeshadowingItem[]>(() => {
  const items: ForeshadowingItem[] = []
  for (const outline of props.outlines || []) {
    const prediction = outline.metadata?.prediction
    if (!prediction) continue
    for (const hook of prediction.foreshadowing_hooks || []) {
      items.push({ chapter: outline.chapter_number, type: 'hook', text: hook })
    }
    for (const target of prediction.foreshadowing_targets || []) {
      items.push({ chapter: outline.chapter_number, type: 'target', text: target })
    }
  }
  return items.sort((a, b) => a.chapter - b.chapter)
})
</script>

<style scoped>
/* 遮罩层过渡 */
.codex-overlay-enter-active,
.codex-overlay-leave-active {
  transition: opacity 0.25s ease;
}
.codex-overlay-enter-from,
.codex-overlay-leave-to {
  opacity: 0;
}

/* 面板滑入过渡 */
.codex-panel-enter-active,
.codex-panel-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.codex-panel-enter-from,
.codex-panel-leave-to {
  transform: translateX(100%);
}

.m3-chip-warning {
  background-color: #fff3e0;
  color: #e65100;
}
</style>
