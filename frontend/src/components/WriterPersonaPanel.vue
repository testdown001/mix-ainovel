<!-- AIMETA P=写手人格配置界面_风格对齐_FewShot|R=写作风格_范文参考_人物模型|NR=不含LLM生成入口|E=component:WriterPersonaPanel|X=ui|A=组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="bg-bg-surface rounded-2xl border border-border p-6 relative">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-text-primary to-text-muted">
        Writer Persona 设定 (Beta)
      </h3>
      <div class="flex items-center space-x-2">
        <span class="text-sm" :class="form.is_active ? 'text-success font-medium' : 'text-text-muted'">
          {{ form.is_active ? '已启用' : '已停用' }}
        </span>
        <button
          @click="toggleActive"
          class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          :class="form.is_active ? 'bg-primary' : 'bg-bg-highlight'"
          role="switch"
          :aria-checked="form.is_active"
        >
          <span
            aria-hidden="true"
            class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-bg-surface shadow ring-0 transition duration-200 ease-in-out"
            :class="form.is_active ? 'translate-x-5' : 'translate-x-0'"
          ></span>
        </button>
      </div>
    </div>

    <!-- 骨架屏加载状态 -->
    <div v-if="loading" class="animate-pulse space-y-4">
      <div class="h-4 bg-bg-highlight rounded w-1/4"></div>
      <div class="space-y-3">
        <div class="h-8 bg-bg-highlight rounded"></div>
        <div class="h-8 bg-bg-highlight rounded w-5/6"></div>
      </div>
    </div>

    <div v-else class="space-y-6" :class="{ 'opacity-50 pointer-events-none': !form.is_active }">
      <!-- 基础设定 -->
      <div>
        <label class="block text-sm font-medium text-text-secondary mb-1">写手标识 / 别名</label>
        <input
          type="text"
          v-model="form.name"
          placeholder="例如：起点爽文写手、诡秘之主同人作者"
          class="block w-full rounded-lg border-border focus:border-border-focus focus:ring-primary/10 sm:text-sm px-4 py-2 border bg-bg-surface"
        />
      </div>

      <!-- Show, Don't Tell 设定 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-bg-elevated/50 rounded-xl border border-border">
        <div class="md:col-span-2">
          <h4 class="text-md font-semibold text-text-primary mb-2 flex items-center">
            <svg class="h-5 w-5 mr-1 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            展示与叙述 (Show, Don't Tell)
          </h4>
          <p class="text-xs text-text-muted">使用生理反应、物理现象来替代空洞的情绪形容词（如“他很生气”）。</p>
        </div>

        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">描写风格</label>
          <input
             v-model="form.description_style"
             placeholder="镜头语言，画面感强，少用形容词"
             class="block w-full rounded-lg border-border focus:border-border-focus focus:ring-primary/10 sm:text-sm px-3 py-2 border bg-bg-surface"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">展示与叙述比例</label>
          <input
             v-model="form.show_vs_tell_ratio"
             placeholder="7:3 展示为主"
             class="block w-full rounded-lg border-border focus:border-border-focus focus:ring-primary/10 sm:text-sm px-3 py-2 border bg-bg-surface"
          />
        </div>

        <div class="md:col-span-2">
          <label class="block text-sm font-medium text-text-secondary mb-1">感官词汇偏好 (用 Enter 添加)</label>
          <ArrayInput v-model="form.sensory_focus!" placeholder="视觉、听觉、触觉..." />
        </div>

        <div class="md:col-span-2">
          <label class="block text-sm font-medium text-text-secondary mb-1">生理反应参照 (替代抽象情绪形容词)</label>
          <ArrayInput v-model="form.physiological_reactions!" placeholder="瞳孔收缩、后背微发凉..." />
        </div>
      </div>

      <!-- Few-Shot 标杆对齐 -->
      <div class="p-4 bg-primary-muted/50 rounded-xl border border-border">
        <h4 class="text-md font-semibold text-text-primary mb-2 flex items-center">
          <svg class="h-5 w-5 mr-1 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          文本标杆 (Few-Shot Alignment)
        </h4>
        <p class="text-xs text-text-muted mb-3">提供您认为的高密度、高质量文段。AI 将严格学习其动词节奏和画面质感。</p>
        
        <div class="space-y-3">
          <div v-for="(text, index) in (form.benchmark_texts || [])" :key="index" class="relative group">
            <textarea
              v-model="form.benchmark_texts![index]"
              rows="3"
              class="block w-full rounded-lg border-border focus:border-border-focus focus:ring-primary/10 sm:text-sm px-4 py-2 border bg-bg-surface group-hover:bg-bg-elevated transition-colors resize-y"
              :placeholder="'标杆文段 ' + (index + 1)"
            ></textarea>
            <button @click="removeBenchmark(index)" class="absolute top-2 right-2 text-text-muted hover:text-red-500 p-1 bg-bg-surface rounded backdrop-blur opacity-0 group-hover:opacity-100 transition-opacity">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>
          <button @click="addBenchmark" class="text-sm text-primary hover:text-primary flex items-center px-2 py-1 rounded hover:bg-primary-muted transition-colors">
            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
            添加一段标杆文本
          </button>
        </div>
      </div>

      <!-- 反 AI 探测机制 -->
      <div>
        <h4 class="text-md font-medium text-text-primary mb-2">人类化特征 (Anti-AI Detection)</h4>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-text-secondary mb-1">角色口头禅</label>
            <ArrayInput v-model="form.catchphrases!" placeholder="说实话、懂的都懂..." />
          </div>
          <div>
            <label class="block text-xs font-medium text-text-secondary mb-1">写手小习惯</label>
            <ArrayInput v-model="form.personal_quirks!" placeholder="关键对话后加一句内心吐槽..." />
          </div>
        </div>
      </div>

    </div>

    <!-- 底部操作区 -->
    <div class="mt-6 flex justify-end space-x-3 border-t border-border pt-4">
      <button
        @click="savePersona"
        :disabled="saving"
        class="inline-flex items-center px-4 py-2 border border-transparent rounded-lg text-sm font-medium text-on-primary bg-primary hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary/10 disabled:opacity-40 transition-colors"
      >
        <svg v-if="saving" class="animate-spin -ml-1 mr-2 h-4 w-4 text-on-primary" fill="none" viewBox="0 0 24 24">
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
