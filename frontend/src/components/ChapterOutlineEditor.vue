<!-- AIMETA P=章节大纲编辑_大纲编辑器|R=大纲编辑_AI推演|NR=不含章节内容|E=component:ChapterOutlineEditor|X=internal|A=编辑器|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="space-y-4">
    <!-- AI推演面板 -->
    <div v-if="props.projectId" class="border border-border rounded-lg bg-primary-muted/50">
      <button
        type="button"
        class="flex items-center gap-1.5 w-full px-4 py-2.5 text-sm font-medium text-primary hover:bg-primary-muted/50 rounded-lg transition-colors"
        @click="showInferPanel = !showInferPanel"
      >
        <svg
          class="w-4 h-4 transition-transform duration-200"
          :class="{ 'rotate-90': showInferPanel }"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
        </svg>
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        AI推演大纲
      </button>

      <div v-if="showInferPanel" class="px-4 pb-4 space-y-3">
        <!-- 参数行 -->
        <div class="flex items-center gap-4 flex-wrap">
          <label class="flex items-center gap-1.5 text-sm text-text-secondary">
            从第
            <input
              v-model.number="inferStartChapter"
              type="number"
              min="1"
              class="w-16 px-2 py-1 border border-border rounded text-center text-sm focus:ring-1 focus:ring-primary/10 focus:border-border-focus"
            />
            章开始
          </label>
          <label class="flex items-center gap-1.5 text-sm text-text-secondary">
            生成
            <input
              v-model.number="inferNumChapters"
              type="number"
              min="1"
              max="50"
              class="w-16 px-2 py-1 border border-border rounded text-center text-sm focus:ring-1 focus:ring-primary/10 focus:border-border-focus"
            />
            章
          </label>
        </div>

        <!-- 排除内容（可折叠） -->
        <div>
          <button
            type="button"
            class="flex items-center gap-1 text-sm text-text-muted hover:text-text-secondary transition-colors"
            @click="showExclusions = !showExclusions"
          >
            <svg
              class="w-3.5 h-3.5 transition-transform duration-200"
              :class="{ 'rotate-90': showExclusions }"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
            排除内容（可选）
          </button>
          <textarea
            v-if="showExclusions"
            v-model="exclusions"
            placeholder="禁止推演出现的内容，例如：不要后宫、不要重生穿越、禁止无脑打脸升级..."
            rows="2"
            class="mt-1.5 w-full p-2 border border-border rounded-md text-sm focus:ring-1 focus:ring-primary/10 focus:border-border-focus transition"
          ></textarea>
        </div>

        <!-- 推演按钮与状态 -->
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-on-primary bg-primary hover:bg-primary-hover rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isInferring"
            @click="handleAiInfer"
          >
            <svg v-if="isInferring" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {{ inferButtonText }}
          </button>
          <span v-if="inferError" class="text-sm text-error">{{ inferError }}</span>
          <span v-if="inferStep === 'done'" class="text-sm text-emerald-600">推演完成，伏笔已同步</span>
        </div>
      </div>
    </div>

    <!-- 大纲列表 -->
    <div class="max-h-96 overflow-y-auto p-1 space-y-4">
      <div v-for="(chapter, index) in localOutline" :key="index" class="p-4 border border-border rounded-lg bg-bg-elevated">
        <div class="flex items-center mb-2">
          <span class="font-bold text-primary mr-2">第 {{ chapter.chapter_number }} 章</span>
          <input
            type="text"
            v-model="chapter.title"
            class="flex-grow p-1 border-b-2 border-border focus:border-border-focus outline-none transition"
            placeholder="章节标题"
          />
          <button @click="removeChapter(index)" class="ml-2 text-red-400 hover:text-red-600 transition-colors p-1">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        <textarea
          v-model="chapter.summary"
          class="w-full h-24 p-2 mt-2 border border-border rounded-md focus:ring-1 focus:ring-primary/10 focus:border-border-focus transition text-sm"
          placeholder="章节摘要"
        ></textarea>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import { NovelAPI } from '@/api/novel';
import type { ChapterOutline } from '@/api/novel';

const props = defineProps({
  modelValue: {
    type: Array as () => ChapterOutline[],
    default: () => []
  },
  projectId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue']);

const localOutline = ref<ChapterOutline[]>([]);
let syncing = false;

// AI推演相关状态
const showInferPanel = ref(false);
const showExclusions = ref(false);
const exclusions = ref('');
const inferNumChapters = ref(5);
const isInferring = ref(false);
const inferStep = ref<'idle' | 'generating' | 'syncing' | 'done'>('idle');
const inferError = ref('');

const inferStartChapter = ref(1);

const inferButtonText = computed(() => {
  switch (inferStep.value) {
    case 'generating': return '推演中...';
    case 'syncing': return '同步伏笔中...';
    default: return '开始推演';
  }
});

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localOutline.value = JSON.parse(JSON.stringify(newVal || []));
  // 更新推演起始章号默认值
  const arr = newVal || [];
  inferStartChapter.value = arr.length > 0
    ? Math.max(...arr.map(o => o.chapter_number)) + 1
    : 1;
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localOutline, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', JSON.parse(JSON.stringify(newVal)));
}, { deep: true });

const removeChapter = (index: number) => {
  localOutline.value.splice(index, 1);
  localOutline.value.forEach((chapter, i) => {
    chapter.chapter_number = i + 1;
  });
};

const handleAiInfer = async () => {
  if (isInferring.value || !props.projectId) return;
  isInferring.value = true;
  inferStep.value = 'generating';
  inferError.value = '';

  try {
    // 拼装 userPrompt，将排除内容以创作禁区标记注入
    let userPrompt = '';
    if (exclusions.value.trim()) {
      userPrompt = `【创作禁区】以下内容禁止出现在大纲中：\n${exclusions.value.trim()}`;
    }

    // Step 1: 调用已有的大纲生成API
    const result = await NovelAPI.generateChapterOutline(
      props.projectId,
      inferStartChapter.value,
      inferNumChapters.value,
      undefined,
      userPrompt || undefined
    );

    // Step 2: 用返回数据更新本地大纲
    const newOutline = result.blueprint?.chapter_outline || [];
    if (newOutline.length > 0) {
      syncing = true;
      localOutline.value = JSON.parse(JSON.stringify(newOutline));
      emit('update:modelValue', JSON.parse(JSON.stringify(newOutline)));
      await nextTick();
      syncing = false;
    }

    // Step 3: 自动同步伏笔（同时清理无效角色伏笔）
    inferStep.value = 'syncing';
    try {
      await NovelAPI.generateForeshadowings(props.projectId);
    } catch (e) {
      console.warn('伏笔同步失败（不影响大纲推演结果）:', e);
    }

    inferStep.value = 'done';
    setTimeout(() => {
      if (inferStep.value === 'done') inferStep.value = 'idle';
    }, 3000);
  } catch (e: any) {
    console.error('AI推演失败:', e);
    inferError.value = e instanceof Error ? e.message : 'AI推演失败，请重试';
    inferStep.value = 'idle';
  } finally {
    isInferring.value = false;
  }
};
</script>
