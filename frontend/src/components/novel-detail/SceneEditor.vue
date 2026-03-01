<!-- 场景编辑器 - 嵌入在章节大纲卡片中 -->
<template>
  <div class="mt-3 border-t pt-3" style="border-color: var(--md-outline-variant);">
    <div class="flex items-center justify-between mb-2">
      <button
        class="flex items-center gap-1.5 text-sm font-medium transition-colors"
        style="color: var(--md-primary);"
        @click="expanded = !expanded"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-4 w-4 transition-transform"
          :class="{ 'rotate-90': expanded }"
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
        🎬 场景 ({{ scenes.length }})
      </button>
      <div v-if="expanded" class="flex gap-2">
        <button
          class="px-2 py-1 text-xs font-medium rounded-md transition-colors"
          style="color: var(--md-primary); background: var(--md-primary-container);"
          :disabled="isGenerating"
          @click="generateScenes"
        >
          {{ isGenerating ? '拆分中...' : 'AI拆分' }}
        </button>
        <button
          class="px-2 py-1 text-xs font-medium rounded-md transition-colors"
          style="color: var(--md-on-surface-variant); background: var(--md-surface-container);"
          @click="addScene"
        >
          + 添加
        </button>
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="msg" class="mb-2 p-2 rounded text-xs" :class="msgType === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">
      {{ msg }}
    </div>

    <!-- 场景列表 -->
    <div v-if="expanded" class="space-y-2">
      <div v-if="scenes.length === 0" class="text-center py-4">
        <p class="text-sm" style="color: var(--md-on-surface-variant);">暂无场景，点击"AI拆分"自动生成</p>
      </div>

      <div
        v-for="(scene, idx) in scenes"
        :key="idx"
        class="p-3 rounded-lg border text-sm relative group"
        :style="`border-color: var(--md-outline-variant); background: var(--md-surface-container-lowest);`"
      >
        <!-- 删除按钮 -->
        <button
          class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-red-400 hover:text-red-600 p-0.5"
          @click="removeScene(idx)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>

        <div class="flex items-start gap-2">
          <span class="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white" :style="`background: ${moodColors[scene.mood] || '#94a3b8'}`">
            {{ idx + 1 }}
          </span>
          <div class="flex-1 min-w-0">
            <input
              v-model="scene.title"
              class="font-semibold w-full bg-transparent border-none p-0 text-sm focus:outline-none"
              style="color: var(--md-on-surface);"
              placeholder="场景标题"
              @blur="saveScenes"
            />
            <textarea
              v-model="scene.summary"
              class="w-full bg-transparent border-none p-0 text-xs mt-1 resize-none focus:outline-none"
              style="color: var(--md-on-surface-variant);"
              placeholder="场景摘要..."
              rows="2"
              @blur="saveScenes"
            ></textarea>
            <div class="flex flex-wrap gap-2 mt-1.5">
              <span v-if="scene.location" class="text-xs px-1.5 py-0.5 rounded bg-green-50 text-green-600">📍 {{ scene.location }}</span>
              <span v-if="scene.mood" class="text-xs px-1.5 py-0.5 rounded" :style="`background: ${moodColors[scene.mood] || '#f1f5f9'}20; color: ${moodColors[scene.mood] || '#64748b'};`">
                🎭 {{ scene.mood }}
              </span>
              <span v-for="char in (scene.characters || [])" :key="char" class="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600">
                👤 {{ char }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { NovelAPI } from '@/api/novel'

interface Scene {
  title: string
  summary: string
  location: string
  characters: string[]
  mood: string
}

const props = defineProps<{
  projectId: string
  chapterNumber: number
  initialScenes?: Scene[]
}>()

const expanded = ref(false)
const scenes = ref<Scene[]>([])
const isGenerating = ref(false)
const msg = ref('')
const msgType = ref<'success' | 'error'>('success')

const moodColors: Record<string, string> = {
  '紧张': '#ef4444',
  '温馨': '#f59e0b',
  '悲伤': '#3b82f6',
  '轻松': '#10b981',
  '激烈': '#dc2626',
  '神秘': '#8b5cf6',
  '压抑': '#6b7280',
  '欢快': '#f97316',
  '平静': '#06b6d4',
}

const showMsg = (m: string, type: 'success' | 'error') => {
  msg.value = m
  msgType.value = type
  setTimeout(() => { msg.value = '' }, 3000)
}

const loadScenes = async () => {
  try {
    const result = await NovelAPI.getChapterScenes(props.projectId, props.chapterNumber)
    scenes.value = result.scenes || []
  } catch (e) {
    // 可能没有场景数据，这是正常的
    scenes.value = props.initialScenes || []
  }
}

const saveScenes = async () => {
  try {
    await NovelAPI.updateChapterScenes(props.projectId, props.chapterNumber, scenes.value)
  } catch (e: any) {
    showMsg('保存失败', 'error')
  }
}

const addScene = () => {
  scenes.value.push({
    title: `场景 ${scenes.value.length + 1}`,
    summary: '',
    location: '',
    characters: [],
    mood: '',
  })
  saveScenes()
}

const removeScene = (idx: number) => {
  scenes.value.splice(idx, 1)
  saveScenes()
}

const generateScenes = async () => {
  isGenerating.value = true
  try {
    const result = await NovelAPI.generateChapterScenes(props.projectId, props.chapterNumber)
    scenes.value = result.scenes || []
    showMsg(result.message, 'success')
    expanded.value = true
  } catch (e: any) {
    showMsg(e.message || '拆分失败', 'error')
  } finally {
    isGenerating.value = false
  }
}

watch(() => props.chapterNumber, loadScenes)
onMounted(loadScenes)
</script>
