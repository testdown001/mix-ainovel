<!-- AIMETA P=写作偏好设置_风格配置界面|R=预设选择_自定义规则_禁用词|NR=不含LLM调用|E=component:WritingPreferences|X=ui|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <h2 class="text-2xl font-bold text-gray-800 mb-2">写作风格偏好</h2>
    <p class="text-sm text-gray-500 mb-6">选择预设风格或自定义规则，保存后所有项目的章节生成自动生效。</p>

    <div v-if="loading" class="text-center text-gray-400 py-12">加载中...</div>

    <div v-else class="space-y-8">
      <!-- 预设选择 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-3">风格预设</label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- 无预设 -->
          <div
            @click="form.style_preset = null"
            class="border-2 rounded-xl p-4 cursor-pointer transition-all"
            :class="form.style_preset === null
              ? 'border-indigo-500 bg-indigo-50'
              : 'border-gray-200 hover:border-gray-300'"
          >
            <div class="font-medium text-gray-800">不使用预设</div>
            <div class="text-xs text-gray-500 mt-1">仅使用自定义规则和禁用词</div>
          </div>
          <!-- 预设卡片 -->
          <div
            v-for="preset in presets"
            :key="preset.key"
            @click="selectPreset(preset.key)"
            class="border-2 rounded-xl p-4 cursor-pointer transition-all"
            :class="form.style_preset === preset.key
              ? 'border-indigo-500 bg-indigo-50'
              : 'border-gray-200 hover:border-gray-300'"
          >
            <div class="font-medium text-gray-800">{{ preset.name }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ preset.description }}</div>
          </div>
        </div>
      </div>

      <!-- 自定义规则 -->
      <div>
        <label for="custom-rules" class="block text-sm font-medium text-gray-700 mb-1">自定义写作规则</label>
        <p class="text-xs text-gray-400 mb-2">输入你希望 AI 在写作时遵守的额外规则，与预设叠加生效。</p>
        <textarea
          id="custom-rules"
          v-model="form.custom_rules"
          rows="5"
          class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm resize-y"
          placeholder="例如：对话占比不低于30%；避免连续三段以上的纯叙述..."
        ></textarea>
      </div>

      <!-- 禁用词管理 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">自定义禁用词</label>
        <p class="text-xs text-gray-400 mb-2">这些词汇/句式将被禁止在生成内容中出现（与预设自带禁用词叠加）。</p>
        <div class="flex flex-wrap gap-2 mb-3">
          <span
            v-for="(phrase, index) in form.banned_phrases"
            :key="index"
            class="inline-flex items-center gap-1 px-3 py-1 bg-red-50 text-red-700 text-sm rounded-full border border-red-200"
          >
            {{ phrase }}
            <button
              type="button"
              @click="removePhrase(index)"
              class="text-red-400 hover:text-red-600"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
          </span>
          <span v-if="form.banned_phrases.length === 0" class="text-sm text-gray-400">暂无自定义禁用词</span>
        </div>
        <div class="flex gap-2">
          <input
            type="text"
            v-model="newPhrase"
            @keydown.enter.prevent="addPhrase"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            placeholder="输入禁用词后按回车添加"
          >
          <button
            type="button"
            @click="addPhrase"
            class="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors text-sm"
          >
            添加
          </button>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex justify-end space-x-4 pt-4">
        <button
          type="button"
          @click="handleReset"
          class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          重置
        </button>
        <button
          type="button"
          @click="handleSave"
          :disabled="saving"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:bg-indigo-400 disabled:cursor-not-allowed"
        >
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import {
  getWritingPreference,
  saveWritingPreference,
  deleteWritingPreference,
  getPresets,
  type PresetInfo,
} from '@/api/writingPreferences';

const loading = ref(true);
const saving = ref(false);
const presets = ref<PresetInfo[]>([]);
const newPhrase = ref('');

const form = reactive({
  style_preset: null as string | null,
  custom_rules: '',
  banned_phrases: [] as string[],
});

onMounted(async () => {
  try {
    const [presetsData, existing] = await Promise.all([getPresets(), getWritingPreference()]);
    presets.value = presetsData;
    if (existing) {
      form.style_preset = existing.style_preset;
      form.custom_rules = existing.custom_rules || '';
      form.banned_phrases = existing.banned_phrases || [];
    }
  } catch (e) {
    console.error('Failed to load writing preferences:', e);
  } finally {
    loading.value = false;
  }
});

const selectPreset = (key: string) => {
  form.style_preset = form.style_preset === key ? null : key;
};

const addPhrase = () => {
  const phrase = newPhrase.value.trim();
  if (phrase && !form.banned_phrases.includes(phrase)) {
    form.banned_phrases.push(phrase);
    newPhrase.value = '';
  }
};

const removePhrase = (index: number) => {
  form.banned_phrases.splice(index, 1);
};

const handleSave = async () => {
  saving.value = true;
  try {
    await saveWritingPreference({
      style_preset: form.style_preset,
      custom_rules: form.custom_rules || null,
      banned_phrases: form.banned_phrases.length > 0 ? form.banned_phrases : null,
    });
    alert('写作偏好已保存！');
  } catch (e) {
    console.error('Failed to save:', e);
    alert('保存失败，请重试');
  } finally {
    saving.value = false;
  }
};

const handleReset = async () => {
  if (!confirm('确定要重置写作偏好吗？将清除所有已保存的设置。')) return;
  try {
    await deleteWritingPreference();
    form.style_preset = null;
    form.custom_rules = '';
    form.banned_phrases = [];
    alert('写作偏好已重置！');
  } catch {
    // 404 is fine — nothing to delete
    form.style_preset = null;
    form.custom_rules = '';
    form.banned_phrases = [];
  }
};
</script>
