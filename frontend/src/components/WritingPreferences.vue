<!-- AIMETA P=写作偏好设置_风格配置界面|R=预设选择_自定义规则_禁用词|NR=不含LLM调用|E=component:WritingPreferences|X=ui|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div>
    <h2 class="text-base font-bold text-white mb-1">写作风格偏好</h2>
    <p class="text-xs mb-6" style="color:#888888;">选择预设风格或自定义规则，保存后所有项目的章节生成自动生效。</p>

    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="md-spinner"></div>
    </div>

    <div v-else class="space-y-7">
      <!-- Style presets -->
      <div>
        <label class="block text-xs font-medium mb-3" style="color:#888888;">风格预设</label>
        <div class="grid grid-cols-2 gap-3">
          <div @click="form.style_preset = null"
            class="border rounded-xl p-4 cursor-pointer transition-all"
            :style="form.style_preset === null
              ? 'border-color:#FFE500; background:#1A1600;'
              : 'border-color:#2A2A2A; background:#141414;'">
            <div class="text-sm font-medium text-white">不使用预设</div>
            <div class="text-xs mt-1" style="color:#888888;">仅使用自定义规则和禁用词</div>
          </div>
          <div v-for="preset in presets" :key="preset.key"
            @click="selectPreset(preset.key)"
            class="border rounded-xl p-4 cursor-pointer transition-all"
            :style="form.style_preset === preset.key
              ? 'border-color:#FFE500; background:#1A1600;'
              : 'border-color:#2A2A2A; background:#141414;'">
            <div class="text-sm font-medium text-white">{{ preset.name }}</div>
            <div class="text-xs mt-1" style="color:#888888;">{{ preset.description }}</div>
            <div v-if="FAST_INCOMPATIBLE_PRESETS.has(preset.key)" class="text-[11px] mt-1.5" style="color:#B8860B;">
              快速档生成时不生效（该档位固定网文节奏）
            </div>
          </div>
        </div>
      </div>

      <!-- Custom rules -->
      <div>
        <label for="custom-rules" class="block text-xs font-medium mb-1" style="color:#888888;">自定义写作规则</label>
        <p class="text-[11px] mb-2" style="color:#555555;">输入你希望 AI 在写作时遵守的额外规则，与预设叠加生效。</p>
        <textarea id="custom-rules" v-model="form.custom_rules" rows="5"
          class="block w-full px-3 py-2.5 rounded-lg text-sm resize-y transition-colors"
          style="background:#141414; border:1px solid #2A2A2A; color:#FFFFFF; outline:none;"
          placeholder="例如：对话占比不低于30%；避免连续三段以上的纯叙述..."
          @focus="($event.target as HTMLElement).style.borderColor='#FFE500'"
          @blur="($event.target as HTMLElement).style.borderColor='#2A2A2A'"
        ></textarea>
      </div>

      <!-- Banned phrases -->
      <div>
        <label class="block text-xs font-medium mb-1" style="color:#888888;">自定义禁用词</label>
        <p class="text-[11px] mb-3" style="color:#555555;">这些词汇/句式将被禁止在生成内容中出现（与预设自带禁用词叠加）。</p>
        <div class="flex flex-wrap gap-2 mb-3 min-h-[28px]">
          <span v-for="(phrase, index) in form.banned_phrases" :key="index"
            class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium"
            style="background:#3D0A0A; color:#FF9EB8; border:1px solid #5A1515;">
            {{ phrase }}
            <button type="button" @click="removePhrase(index)"
              class="transition-colors" style="color:#FF4757;">
              <svg class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
              </svg>
            </button>
          </span>
          <span v-if="form.banned_phrases.length === 0" class="text-xs" style="color:#555555;">暂无自定义禁用词</span>
        </div>
        <div class="flex gap-2">
          <input type="text" v-model="newPhrase" @keydown.enter.prevent="addPhrase"
            class="flex-1 px-3 py-2.5 rounded-lg text-sm transition-colors"
            style="background:#141414; border:1px solid #2A2A2A; color:#FFFFFF; outline:none;"
            placeholder="输入禁用词后按回车添加"
            @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
            @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'"
          />
          <button type="button" @click="addPhrase"
            class="px-4 py-2.5 rounded-lg text-sm font-medium flex-shrink-0 transition-colors"
            style="background:#1C1C1C; border:1px solid #2A2A2A; color:#888888;">
            添加
          </button>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-3 pt-2">
        <button type="button" @click="handleReset"
          class="px-4 py-2 rounded-lg text-sm font-medium"
          style="background:transparent; border:1px solid #3D0A0A; color:#FF4757;">
          重置
        </button>
        <button type="button" @click="handleSave" :disabled="saving"
          class="px-5 py-2 rounded-lg text-sm font-semibold transition-colors"
          :style="saving ? 'background:#888;color:#000;' : 'background:#FFE500;color:#000;'">
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

// 与后端 core/writing_strategy.py DEFAULT_COMPATIBILITY 对齐：fast 档
// incompatible_styles + on_conflict=ignore_style，即这两个预设在快速档静默失效
const FAST_INCOMPATIBLE_PRESETS = new Set(['classic_elegant', 'minimal_concrete']);

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

const selectPreset = (key: string) => { form.style_preset = form.style_preset === key ? null : key; };
const addPhrase = () => {
  const phrase = newPhrase.value.trim();
  if (phrase && !form.banned_phrases.includes(phrase)) { form.banned_phrases.push(phrase); newPhrase.value = ''; }
};
const removePhrase = (index: number) => { form.banned_phrases.splice(index, 1); };

const handleSave = async () => {
  saving.value = true;
  try {
    await saveWritingPreference({
      style_preset: form.style_preset,
      custom_rules: form.custom_rules || null,
      banned_phrases: form.banned_phrases.length > 0 ? form.banned_phrases : null,
    });
    alert('写作偏好已保存！');
  } catch {
    alert('保存失败，请重试');
  } finally {
    saving.value = false;
  }
};

const handleReset = async () => {
  if (!confirm('确定要重置写作偏好吗？将清除所有已保存的设置。')) return;
  try {
    await deleteWritingPreference();
  } catch { /* 404 is fine */ }
  form.style_preset = null;
  form.custom_rules = '';
  form.banned_phrases = [];
  alert('写作偏好已重置！');
};
</script>
