<!-- AIMETA P=世界观设定典面板|R=角色世界观关系伏笔宪法审稿可编辑|NR=不含章节生成|E=component:WDCodexPanel|X=ui|A=抽屉面板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <Teleport to="body">
    <Transition name="codex-overlay">
      <div
        v-if="visible"
        class="fixed inset-0 z-40"
        style="background-color: rgba(0, 0, 0, 0.32);"
        @click="$emit('update:visible', false)"
      />
    </Transition>

    <Transition name="codex-panel">
      <div
        v-if="visible"
        class="fixed top-0 right-0 h-full w-[26rem] z-50 flex flex-col overflow-hidden"
        style="background-color: var(--md-surface); box-shadow: var(--md-elevation-3);"
      >
        <div class="flex items-center justify-between px-5 py-4 flex-shrink-0" style="border-bottom: 1px solid var(--md-outline-variant);">
          <div>
            <h2 class="md-title-large font-semibold" style="color: var(--md-on-surface);">世界观设定典</h2>
            <p class="md-body-small md-on-surface-variant mt-0.5">生成时会注入。改完请保存。</p>
          </div>
          <div class="flex items-center gap-2">
            <button class="md-btn md-btn-text !px-2 !py-1 text-xs" @click="editing = !editing">
              {{ editing ? '退出编辑' : '编辑' }}
            </button>
            <button @click="$emit('update:visible', false)" class="md-icon-btn md-ripple">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
              </svg>
            </button>
          </div>
        </div>

        <div class="flex flex-shrink-0 px-1 overflow-x-auto" style="border-bottom: 1px solid var(--md-outline-variant);">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            class="flex-1 min-w-[4.2rem] py-3 text-center md-label-large transition-colors relative"
            :style="{ color: activeTab === tab.key ? 'var(--md-primary)' : 'var(--md-on-surface-variant)' }"
          >
            {{ tab.label }}
            <span v-if="activeTab === tab.key" class="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full" style="background-color: var(--md-primary);" />
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          <template v-if="activeTab === 'characters'">
            <div v-if="!draftCharacters.length" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无角色。蓝图锁定后会自动播种，也可点编辑补上。
            </div>
            <div v-for="(char, i) in draftCharacters" :key="char.name + i" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
              <template v-if="editing">
                <input v-model="char.name" class="md-input w-full mb-2" placeholder="角色名" />
                <input v-model="char.identity" class="md-input w-full mb-2" placeholder="身份" />
                <textarea v-model="char.description" rows="2" class="md-textarea w-full mb-2" placeholder="简介（生成时会注入）" />
                <textarea v-model="char.personality" rows="2" class="md-textarea w-full" placeholder="性格" />
              </template>
              <template v-else>
                <div class="flex items-center gap-2 mb-1">
                  <span class="md-title-small font-semibold">{{ char.name }}</span>
                  <span v-if="isRelevant(char.name)" class="md-chip m3-chip-success !text-[10px] !px-1.5 !py-0">本章相关</span>
                  <span v-if="char.identity" class="md-body-small md-on-surface-variant">{{ char.identity }}</span>
                </div>
                <p class="md-body-small md-on-surface-variant">{{ char.description }}</p>
              </template>
            </div>
            <button v-if="editing" class="md-btn md-btn-tonal w-full" @click="addCharacter">新增角色</button>
            <button v-if="editing" class="md-btn md-btn-filled w-full" :disabled="saving" @click="saveBlueprintPatch">
              {{ saving ? '保存中…' : '保存角色与设定' }}
            </button>
          </template>

          <template v-if="activeTab === 'world'">
            <div v-if="!hasWorldData && !editing" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无世界观。编辑后写入蓝图，下次起草会注入。
            </div>
            <div class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
              <h4 class="md-title-small font-semibold mb-2">核心规则</h4>
              <textarea v-if="editing" v-model="draftWorld.core_rules" rows="4" class="md-textarea w-full" />
              <p v-else class="md-body-small md-on-surface-variant whitespace-pre-line">{{ draftWorld.core_rules || '未填写' }}</p>
            </div>
            <button v-if="editing" class="md-btn md-btn-filled w-full" :disabled="saving" @click="saveBlueprintPatch">
              {{ saving ? '保存中…' : '保存世界观' }}
            </button>
          </template>

          <template v-if="activeTab === 'relations'">
            <div v-if="!draftRelations.length" class="text-center py-8 md-body-medium md-on-surface-variant">暂无关系数据</div>
            <div v-for="(rel, i) in draftRelations" :key="i" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
              <template v-if="editing">
                <div class="flex gap-2 mb-2">
                  <input v-model="rel.from" class="md-input flex-1" placeholder="角色 A" />
                  <input v-model="rel.to" class="md-input flex-1" placeholder="角色 B" />
                </div>
                <textarea v-model="rel.description" rows="2" class="md-textarea w-full" placeholder="关系说明" />
              </template>
              <template v-else>
                <div class="flex items-center gap-2 mb-1">
                  <span class="md-label-large font-semibold">{{ rel.from || rel.character_a || '?' }}</span>
                  <span style="color: var(--md-primary);">→</span>
                  <span class="md-label-large font-semibold">{{ rel.to || rel.character_b || '?' }}</span>
                </div>
                <p class="md-body-small md-on-surface-variant">{{ rel.description || rel.relationship || '' }}</p>
              </template>
            </div>
            <button v-if="editing" class="md-btn md-btn-tonal w-full" @click="draftRelations.push({ from: '', to: '', description: '' })">新增关系</button>
            <button v-if="editing" class="md-btn md-btn-filled w-full" :disabled="saving" @click="saveBlueprintPatch">
              {{ saving ? '保存中…' : '保存关系' }}
            </button>
          </template>

          <template v-if="activeTab === 'foreshadowing'">
            <div v-if="!ledgerItems.length" class="text-center py-8 md-body-medium md-on-surface-variant">
              暂无伏笔台账。生成章节后会抽取，也可手动补一条。
            </div>
            <div v-for="fs in ledgerItems" :key="fs.id" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
              <div class="flex items-center gap-2 mb-1">
                <span class="md-chip !text-[10px] !px-1.5 !py-0">{{ fs.status }}</span>
                <span class="md-label-small md-on-surface-variant">第{{ fs.chapter_number }}章</span>
              </div>
              <textarea v-if="editing" v-model="fs.content" rows="2" class="md-textarea w-full" @blur="saveForeshadow(fs)" />
              <p v-else class="md-body-small md-on-surface">{{ fs.content }}</p>
            </div>
            <div v-if="editing" class="space-y-2">
              <input v-model.number="newFsChapter" type="number" class="md-input w-full" placeholder="埋设章号" />
              <textarea v-model="newFsContent" rows="2" class="md-textarea w-full" placeholder="伏笔内容" />
              <button class="md-btn md-btn-filled w-full" :disabled="saving || !newFsContent" @click="addForeshadow">补一条伏笔</button>
            </div>
          </template>

          <template v-if="activeTab === 'constitution'">
            <p class="md-body-small md-on-surface-variant mb-2">
              蓝图锁定后自动播种。禁写与基调会进入下一次起草的「小说宪法」。
            </p>
            <label class="md-label-small block mb-1">核心主题</label>
            <input v-model="constitution.core_theme" class="md-input w-full mb-3" :disabled="!editing" />
            <label class="md-label-small block mb-1">核心冲突</label>
            <input v-model="constitution.core_conflict" class="md-input w-full mb-3" :disabled="!editing" />
            <label class="md-label-small block mb-1">语言风格</label>
            <input v-model="constitution.language_style" class="md-input w-full mb-3" :disabled="!editing" />
            <label class="md-label-small block mb-1">视角</label>
            <input v-model="constitution.pov_type" class="md-input w-full mb-3" :disabled="!editing" placeholder="第一人称 / 第三人称有限" />
            <label class="md-label-small block mb-1">禁写（每行一条）</label>
            <textarea v-model="forbiddenText" rows="4" class="md-textarea w-full mb-3" :disabled="!editing" placeholder="例如：主角无代价开挂" />
            <button v-if="editing" class="md-btn md-btn-filled w-full" :disabled="saving" @click="saveConstitution">
              {{ saving ? '保存中…' : '保存宪法' }}
            </button>
          </template>

          <template v-if="activeTab === 'review'">
            <BlueprintReviewCard :report="blueprint?.review_report" />
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NovelAPI, type Blueprint, type ChapterOutline, type Character } from '@/api/novel'
import { ProjectAPI, type ConstitutionPayload } from '@/api/project'
import { useNovelStore } from '@/stores/novel'
import { globalAlert } from '@/composables/useAlert'
import BlueprintReviewCard from './BlueprintReviewCard.vue'

interface LedgerItem {
  id: number
  chapter_number: number
  content: string
  status: string
}

interface Props {
  visible: boolean
  projectId: string
  blueprint: Blueprint | null | undefined
  selectedChapterNumber: number | null
  outlines: ChapterOutline[]
}

const props = defineProps<Props>()
defineEmits(['update:visible'])

const novelStore = useNovelStore()
const editing = ref(false)
const saving = ref(false)
const tabs = [
  { key: 'characters', label: '角色' },
  { key: 'world', label: '世界观' },
  { key: 'relations', label: '关系' },
  { key: 'foreshadowing', label: '伏笔' },
  { key: 'constitution', label: '宪法' },
  { key: 'review', label: '审稿' },
] as const
type TabKey = typeof tabs[number]['key']
const activeTab = ref<TabKey>('characters')

const draftCharacters = ref<Character[]>([])
const draftWorld = ref<{ core_rules?: string; key_locations?: any[]; factions?: any[] }>({})
const draftRelations = ref<any[]>([])
const ledgerItems = ref<LedgerItem[]>([])
const constitution = ref<ConstitutionPayload>({})
const forbiddenText = ref('')
const newFsChapter = ref<number>(1)
const newFsContent = ref('')

const currentSummary = computed(() => {
  const outline = props.outlines?.find((o) => o.chapter_number === props.selectedChapterNumber)
  return `${outline?.summary || ''} ${outline?.title || ''}`
})
const isRelevant = (name: string) => name && currentSummary.value.includes(name)
const hasWorldData = computed(() => Boolean(draftWorld.value?.core_rules || draftWorld.value?.key_locations?.length || draftWorld.value?.factions?.length))

function hydrateFromBlueprint() {
  draftCharacters.value = JSON.parse(JSON.stringify(props.blueprint?.characters || []))
  draftWorld.value = JSON.parse(JSON.stringify(props.blueprint?.world_setting || {}))
  draftRelations.value = JSON.parse(JSON.stringify(props.blueprint?.relationships || []))
}

async function loadExtras() {
  if (!props.projectId) return
  try {
    const [fs, cons] = await Promise.all([
      NovelAPI.listForeshadowings(props.projectId),
      ProjectAPI.getConstitution(props.projectId),
    ])
    ledgerItems.value = fs.data || []
    constitution.value = cons.constitution || {}
    const forbidden = constitution.value.forbidden_content
    forbiddenText.value = Array.isArray(forbidden) ? forbidden.join('\n') : (forbidden || '')
  } catch (err) {
    console.warn('设定典附加数据加载失败', err)
  }
}

watch(
  () => [props.visible, props.blueprint],
  ([visible]) => {
    if (visible) {
      hydrateFromBlueprint()
      loadExtras()
    }
  },
  { immediate: true },
)

function addCharacter() {
  draftCharacters.value.push({ name: '', identity: '', description: '', personality: '' } as Character)
}

async function saveBlueprintPatch() {
  if (!props.projectId) return
  saving.value = true
  try {
    const updated = await NovelAPI.updateBlueprint(props.projectId, {
      characters: draftCharacters.value,
      world_setting: draftWorld.value,
      relationships: draftRelations.value,
    })
    novelStore.setCurrentProject(updated)
    editing.value = false
    globalAlert.showSuccess('设定已锁定，下次起草会注入。', '设定典已保存')
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '保存失败', '设定典')
  } finally {
    saving.value = false
  }
}

async function saveConstitution() {
  if (!props.projectId) return
  saving.value = true
  try {
    const payload = {
      ...constitution.value,
      forbidden_content: forbiddenText.value.split('\n').map((s) => s.trim()).filter(Boolean),
    }
    const res = await ProjectAPI.updateConstitution(props.projectId, payload)
    constitution.value = res.constitution
    editing.value = false
    globalAlert.showSuccess('宪法已更新，下次起草会注入禁写与基调。', '宪法已保存')
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '保存失败', '宪法')
  } finally {
    saving.value = false
  }
}

async function saveForeshadow(fs: LedgerItem) {
  if (!props.projectId) return
  try {
    await NovelAPI.updateForeshadowing(props.projectId, fs.id, { content: fs.content })
  } catch (err) {
    console.warn(err)
  }
}

async function addForeshadow() {
  if (!props.projectId || !newFsContent.value.trim()) return
  saving.value = true
  try {
    await NovelAPI.createForeshadowing(props.projectId, {
      chapter_number: Number(newFsChapter.value) || 1,
      content: newFsContent.value.trim(),
    })
    newFsContent.value = ''
    await loadExtras()
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '添加失败', '伏笔')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.codex-overlay-enter-active,
.codex-overlay-leave-active { transition: opacity 0.25s ease; }
.codex-overlay-enter-from,
.codex-overlay-leave-to { opacity: 0; }
.codex-panel-enter-active,
.codex-panel-leave-active { transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.codex-panel-enter-from,
.codex-panel-leave-to { transform: translateX(100%); }
</style>
