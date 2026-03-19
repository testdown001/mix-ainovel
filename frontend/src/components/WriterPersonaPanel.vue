<!-- AIMETA P=写手人格配置界面_风格对齐_FewShot|R=写作风格_范文参考_人物模型|NR=不含LLM生成入口|E=component:WriterPersonaPanel|X=ui|A=组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="wpp-panel">
    <div class="flex items-center justify-between mb-6">
      <h3 class="wpp-title">
        Writer Persona 设定 <span class="wpp-badge">Beta</span>
      </h3>
      <div class="flex items-center space-x-2">
        <span class="text-sm" :style="{ color: form.is_active ? 'var(--ar-secondary)' : 'var(--ar-text-muted)', fontWeight: form.is_active ? '600' : '400' }">
          {{ form.is_active ? '已启用' : '已停用' }}
        </span>
        <button
          @click="toggleActive"
          class="wpp-toggle"
          :class="form.is_active ? 'wpp-toggle--active' : ''"
          role="switch"
          :aria-checked="form.is_active"
        >
          <span
            aria-hidden="true"
            class="wpp-toggle-thumb"
            :class="form.is_active ? 'translate-x-5' : 'translate-x-0'"
          ></span>
        </button>
      </div>
    </div>

    <!-- 骨架屏加载状态 -->
    <div v-if="loading" class="animate-pulse space-y-4">
      <div class="h-4 rounded w-1/4" style="background-color: var(--ar-bg-highlight);"></div>
      <div class="space-y-3">
        <div class="h-8 rounded" style="background-color: var(--ar-bg-highlight);"></div>
        <div class="h-8 rounded w-5/6" style="background-color: var(--ar-bg-highlight);"></div>
      </div>
    </div>

    <div v-else class="space-y-6" :class="{ 'opacity-50 pointer-events-none': !form.is_active }">
      <!-- 基础设定 -->
      <div>
        <label class="wpp-label">写手标识 / 别名</label>
        <input
          type="text"
          v-model="form.name"
          placeholder="例如：起点爽文写手、诡秘之主同人作者"
          class="wpp-input"
        />
      </div>

      <!-- Show, Don't Tell 设定 -->
      <div class="wpp-section">
        <div class="md:col-span-2">
          <h4 class="wpp-section-title">
            <svg class="h-5 w-5 mr-1" style="color: var(--ar-primary);" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            展示与叙述 (Show, Don't Tell)
          </h4>
          <p class="wpp-hint">使用生理反应、物理现象来替代空洞的情绪形容词（如"他很生气"）。</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="wpp-label">描写风格</label>
            <input
               v-model="form.description_style"
               placeholder="镜头语言，画面感强，少用形容词"
               class="wpp-input"
            />
          </div>

          <div>
            <label class="wpp-label">展示与叙述比例</label>
            <input
               v-model="form.show_vs_tell_ratio"
               placeholder="7:3 展示为主"
               class="wpp-input"
            />
          </div>

          <div class="md:col-span-2">
            <label class="wpp-label">感官词汇偏好 (用 Enter 添加)</label>
            <ArrayInput v-model="form.sensory_focus!" placeholder="视觉、听觉、触觉..." />
          </div>

          <div class="md:col-span-2">
            <label class="wpp-label">生理反应参照 (替代抽象情绪形容词)</label>
            <ArrayInput v-model="form.physiological_reactions!" placeholder="瞳孔收缩、后背微发凉..." />
          </div>
        </div>
      </div>

      <!-- Few-Shot 标杆对齐 -->
      <div class="wpp-section wpp-section--accent">
        <h4 class="wpp-section-title">
          <svg class="h-5 w-5 mr-1" style="color: var(--ar-primary);" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          文本标杆 (Few-Shot Alignment)
        </h4>
        <p class="wpp-hint mb-3">提供您认为的高密度、高质量文段。AI 将严格学习其动词节奏和画面质感。</p>
        
        <div class="space-y-3">
          <div v-for="(text, index) in (form.benchmark_texts || [])" :key="index" class="relative group">
            <textarea
              v-model="form.benchmark_texts![index]"
              rows="3"
              class="wpp-textarea"
              :placeholder="'标杆文段 ' + (index + 1)"
            ></textarea>
            <button @click="removeBenchmark(index)" class="wpp-remove-btn">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>
          <button @click="addBenchmark" class="wpp-add-btn">
            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
            添加一段标杆文本
          </button>
        </div>
      </div>

      <!-- 反 AI 探测机制 -->
      <div>
        <h4 class="wpp-section-title mb-2" style="padding: 0;">
          人类化特征 (Anti-AI Detection)
        </h4>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="wpp-label text-xs">角色口头禅</label>
            <ArrayInput v-model="form.catchphrases!" placeholder="说实话、懂的都懂..." />
          </div>
          <div>
            <label class="wpp-label text-xs">写手小习惯</label>
            <ArrayInput v-model="form.personal_quirks!" placeholder="关键对话后加一句内心吐槽..." />
          </div>
        </div>
      </div>

    </div>

    <!-- 底部操作区 -->
    <div class="wpp-footer">
      <button
        @click="savePersona"
        :disabled="saving"
        class="wpp-save-btn"
      >
        <svg v-if="saving" class="animate-spin -ml-1 mr-2 h-4 w-4" style="color: var(--ar-on-primary);" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        保存 Writer 设定
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ProjectAPI, type PersonaPayload } from '@/api/project';
import ArrayInput from './ArrayInput.vue';

const props = defineProps<{
  projectId: string;
}>();

const loading = ref(true);
const saving = ref(false);

const form = reactive<PersonaPayload>({
  is_active: false,
  name: '',
  description_style: '',
  show_vs_tell_ratio: '',
  sensory_focus: [],
  physiological_reactions: [],
  benchmark_texts: [],
  catchphrases: [],
  personal_quirks: []
});

const loadPersona = async () => {
  loading.value = true;
  try {
    const res = await ProjectAPI.getPersona(props.projectId);
    if (res.persona) {
      Object.assign(form, res.persona);
      if (!form.benchmark_texts) form.benchmark_texts = [];
      if (!form.physiological_reactions) form.physiological_reactions = [];
      if (!form.sensory_focus) form.sensory_focus = [];
      if (!form.catchphrases) form.catchphrases = [];
      if (!form.personal_quirks) form.personal_quirks = [];
    }
  } catch (err) {
    console.error('加载 Writer Persona 失败：', err);
  } finally {
    loading.value = false;
  }
};

const savePersona = async () => {
  saving.value = true;
  try {
    // 过滤空的基准测试文本
    const payload = { ...form };
    if (payload.benchmark_texts) {
      payload.benchmark_texts = payload.benchmark_texts.filter(t => t && t.trim().length > 0);
    }
    await ProjectAPI.updatePersona(props.projectId, payload);
    // 可选：添加 Toast 提示成功
  } catch (err) {
    console.error('保存 Writer Persona 失败：', err);
    alert('保存失败，请重试');
  } finally {
    saving.value = false;
  }
};

const toggleActive = () => {
  form.is_active = !form.is_active;
  if (!form.is_active) {
    savePersona(); // 停用时立即保存
  }
};

const addBenchmark = () => {
  if (!form.benchmark_texts) form.benchmark_texts = [];
  form.benchmark_texts.push('');
};

const removeBenchmark = (index: number) => {
  if (form.benchmark_texts) {
    form.benchmark_texts.splice(index, 1);
  }
};

onMounted(() => {
  loadPersona();
});
</script>

<style scoped>
.wpp-panel {
  background-color: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  padding: 24px;
  position: relative;
  box-shadow: var(--ar-elevation-glow);
}

.wpp-title {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-h3);
  font-weight: 700;
  color: var(--ar-text-primary);
}

.wpp-badge {
  display: inline-block;
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-label);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ar-primary);
  background-color: var(--ar-primary-muted);
  padding: 2px 8px;
  border-radius: var(--ar-radius-xs);
  margin-left: 8px;
  vertical-align: middle;
}

/* Toggle switch */
.wpp-toggle {
  position: relative;
  display: inline-flex;
  height: 24px;
  width: 44px;
  flex-shrink: 0;
  cursor: pointer;
  border-radius: var(--ar-radius-full);
  border: 2px solid transparent;
  background-color: var(--ar-bg-highlight);
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.wpp-toggle--active {
  background-color: var(--ar-secondary);
}

.wpp-toggle-thumb {
  pointer-events: none;
  display: inline-block;
  height: 20px;
  width: 20px;
  transform: translateX(0);
  border-radius: var(--ar-radius-full);
  background-color: var(--ar-bg-surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: transform var(--ar-duration-short) var(--ar-easing-standard);
}

/* Form elements */
.wpp-label {
  display: block;
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-label);
  font-weight: 500;
  color: var(--ar-text-secondary);
  margin-bottom: 4px;
  letter-spacing: 0.02em;
}

.wpp-input {
  display: block;
  width: 100%;
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  background-color: var(--ar-bg-surface);
  color: var(--ar-text-primary);
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body);
  padding: 8px 16px;
  outline: none;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.wpp-input:hover {
  background-color: var(--ar-bg-elevated);
}

.wpp-input:focus {
  border-color: var(--ar-border-focus);
  box-shadow: var(--ar-elevation-glow-green);
}

.wpp-input::placeholder {
  color: var(--ar-text-muted);
}

.wpp-textarea {
  display: block;
  width: 100%;
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  background-color: var(--ar-bg-surface);
  color: var(--ar-text-primary);
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body);
  padding: 8px 16px;
  outline: none;
  resize: vertical;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.wpp-textarea:hover {
  background-color: var(--ar-bg-elevated);
}

.wpp-textarea:focus {
  border-color: var(--ar-border-focus);
  box-shadow: var(--ar-elevation-glow-green);
}

.wpp-textarea::placeholder {
  color: var(--ar-text-muted);
}

/* Sections */
.wpp-section {
  padding: 16px;
  background-color: var(--ar-bg-elevated);
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
}

.wpp-section--accent {
  background-color: rgba(250, 204, 21, 0.04);
  border-color: rgba(250, 204, 21, 0.1);
}

.wpp-section-title {
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-h4);
  font-weight: 600;
  color: var(--ar-text-primary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  padding: 0 0 8px 0;
}

.wpp-hint {
  font-size: var(--ar-text-body-sm);
  color: var(--ar-text-muted);
}

/* Buttons */
.wpp-remove-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px;
  color: var(--ar-text-muted);
  background-color: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.group:hover .wpp-remove-btn {
  opacity: 1;
}

.wpp-remove-btn:hover {
  color: var(--ar-error);
  background-color: rgba(239, 68, 68, 0.1);
}

.wpp-add-btn {
  display: inline-flex;
  align-items: center;
  font-size: var(--ar-text-body);
  color: var(--ar-primary);
  padding: 4px 8px;
  border-radius: var(--ar-radius-sm);
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.wpp-add-btn:hover {
  background-color: var(--ar-primary-muted);
}

/* Footer */
.wpp-footer {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid var(--ar-border);
  padding-top: 16px;
}

.wpp-save-btn {
  display: inline-flex;
  align-items: center;
  padding: 8px 16px;
  border: none;
  border-radius: var(--ar-radius-sm);
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body);
  font-weight: 600;
  color: var(--ar-on-primary);
  background: linear-gradient(135deg, var(--ar-primary-dim), var(--ar-primary));
  cursor: pointer;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.wpp-save-btn:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(250, 204, 21, 0.4);
}

.wpp-save-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
