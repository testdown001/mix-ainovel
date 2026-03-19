<!-- AIMETA P=增强角色编辑器_增强版角色编辑|R=增强角色编辑|NR=不含基础功能|E=component:CharactersEditorEnhanced|X=internal|A=增强编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-4 max-h-[600px] overflow-y-auto p-1">
    <!-- 从章节同步角色按钮 -->
    <div v-if="projectId" class="flex items-center justify-between p-3 bg-primary-muted rounded-lg border border-blue-200">
      <div class="flex items-center gap-2">
        <span class="text-blue-600 text-lg">🔄</span>
        <span class="text-sm text-blue-700 font-medium">从章节同步角色</span>
        <span class="text-xs text-text-muted">从已生成章节中提取新增人物</span>
      </div>
      <button
        @click="syncFromChapters"
        :disabled="isSyncing"
        class="px-4 py-1.5 text-sm font-medium text-on-primary bg-primary rounded-md hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
      >
        <svg v-if="isSyncing" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>{{ isSyncing ? '同步中...' : '同步角色' }}</span>
      </button>
    </div>

    <!-- 批量生成DNA按钮 -->
    <div v-if="projectId" class="flex items-center justify-between p-3 bg-purple-50 rounded-lg border border-purple-200">
      <div class="flex items-center gap-2">
        <span class="text-purple-600 text-lg">🧬</span>
        <span class="text-sm text-purple-700 font-medium">角色DNA档案</span>
        <span class="text-xs text-text-muted">基于大纲和剧情自动推演角色心理档案</span>
      </div>
      <button
        @click="generateAllDNA(false)"
        :disabled="isGeneratingDNA"
        class="px-4 py-1.5 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
      >
        <svg v-if="isGeneratingDNA" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>{{ isGeneratingDNA ? '推演中...' : '一键生成全部DNA' }}</span>
      </button>
    </div>
    <!-- DNA生成状态提示 -->
    <div v-if="dnaMessage" class="p-3 rounded-lg text-sm" :class="dnaMessageType === 'success' ? 'bg-success-muted text-success border border-green-200' : dnaMessageType === 'error' ? 'bg-error-muted text-error border border-error/20' : 'bg-primary-muted text-primary border border-blue-200'">
      {{ dnaMessage }}
    </div>

    <div v-for="(character, index) in localCharacters" :key="index" class="p-4 border border-border rounded-lg bg-bg-elevated relative">
      <button @click="removeCharacter(index)" class="absolute top-2 right-2 text-red-400 hover:text-red-600 transition-colors p-1">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>
      
      <!-- 基础信息 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">姓名</label>
          <input type="text" v-model="character.name" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent" />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">身份</label>
          <input type="text" v-model="character.identity" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent" />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">性格</label>
          <input type="text" v-model="character.personality" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent" />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">目标</label>
          <input type="text" v-model="character.goals" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent" />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">能力</label>
          <input type="text" v-model="character.abilities" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent" />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">与主角关系</label>
          <input type="text" v-model="character.relationship_to_protagonist" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent" />
        </div>
        
        <!-- 新增：力量体系选择 -->
        <div>
          <label class="block text-sm font-medium text-text-secondary mb-1">力量体系</label>
          <select v-model="character.power_system_id" @change="character.current_power_level_id = null" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent h-[34px]">
            <option :value="null">无</option>
            <option v-for="ps in powerSystems" :key="ps.id" :value="ps.id">{{ ps.name }}</option>
          </select>
        </div>
        
        <!-- 新增：当前境界选择 -->
        <div v-if="character.power_system_id">
          <label class="block text-sm font-medium text-text-secondary mb-1">当前境界</label>
          <select v-model="character.current_power_level_id" class="w-full p-1 border-b-2 border-border focus:border-border-focus outline-none transition bg-transparent h-[34px]">
            <option :value="null">未知</option>
            <template v-if="powerSystems.find(ps => ps.id === character.power_system_id)">
              <option v-for="lvl in powerSystems.find(ps => ps.id === character.power_system_id)?.levels || []" :key="lvl.id" :value="lvl.id">
                {{ lvl.name }}
              </option>
            </template>
          </select>
        </div>
      </div>

      <!-- DNA档案展开按钮 -->
      <div class="mt-4 border-t border-border pt-3 flex items-center justify-between">
        <button 
          @click="toggleDNA(index)" 
          class="flex items-center gap-2 text-sm font-medium text-purple-600 hover:text-purple-800 transition-colors"
        >
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            class="h-4 w-4 transition-transform" 
            :class="{ 'rotate-90': expandedDNA[index] }"
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
          <span>🧬 角色DNA档案</span>
          <span class="text-xs text-text-muted">(让角色更立体)</span>
        </button>
        <button
          v-if="projectId && character.name"
          @click.stop="generateSingleDNA(character.name)"
          :disabled="isGeneratingDNA"
          class="px-3 py-1 text-xs font-medium text-purple-600 bg-purple-50 border border-purple-200 rounded-md hover:bg-purple-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ isGeneratingDNA ? '推演中...' : 'AI推演' }}
        </button>
      </div>

      <!-- DNA档案内容 -->
      <transition name="slide">
        <div v-if="expandedDNA[index]" class="mt-3 p-4 bg-purple-50 rounded-lg border border-purple-200">
          <div class="grid grid-cols-1 gap-4">
            <!-- 童年经历 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                童年经历/创伤
                <span class="text-xs text-text-muted font-normal ml-1">影响角色的防御机制和情感触发点</span>
              </label>
              <textarea 
                v-model="getDNAProfile(character).childhood_trauma" 
                @input="updateDNA(character, 'childhood_trauma', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：父母离异后由祖母抚养，从小学会察言观色，害怕被抛弃"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
                rows="2"
              ></textarea>
            </div>

            <!-- 核心恐惧 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                核心恐惧
                <span class="text-xs text-text-muted font-normal ml-1">驱动角色行为的深层恐惧</span>
              </label>
              <input 
                type="text"
                v-model="getDNAProfile(character).core_fear"
                @input="updateDNA(character, 'core_fear', ($event.target as HTMLInputElement).value)"
                placeholder="例如：害怕被抛弃、害怕失控、害怕不被爱"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
              />
            </div>

            <!-- 内心渴望 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                内心渴望
                <span class="text-xs text-text-muted font-normal ml-1">角色真正想要的，可能连自己都不清楚</span>
              </label>
              <input 
                type="text"
                v-model="getDNAProfile(character).inner_desire"
                @input="updateDNA(character, 'inner_desire', ($event.target as HTMLInputElement).value)"
                placeholder="例如：渴望被认可、渴望归属感、渴望证明自己"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
              />
            </div>

            <!-- 说话习惯 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                说话习惯
                <span class="text-xs text-text-muted font-normal ml-1">口头禅、语气词、紧张时的变化</span>
              </label>
              <textarea 
                v-model="getDNAProfile(character).speech_habits"
                @input="updateDNA(character, 'speech_habits', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：喜欢用反问句，紧张时语速加快，常说'怎么说呢...'"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
                rows="2"
              ></textarea>
            </div>

            <!-- 身体语言 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                身体语言
                <span class="text-xs text-text-muted font-normal ml-1">紧张时的小动作、特有的姿态</span>
              </label>
              <textarea 
                v-model="getDNAProfile(character).body_language"
                @input="updateDNA(character, 'body_language', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：紧张时会摸耳朵，思考时喜欢转笔，说谎时不敢直视对方"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
                rows="2"
              ></textarea>
            </div>

            <!-- 思维模式 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                思维模式
                <span class="text-xs text-text-muted font-normal ml-1">理性/感性、乐观/悲观</span>
              </label>
              <select 
                v-model="getDNAProfile(character).thinking_pattern"
                @change="updateDNA(character, 'thinking_pattern', ($event.target as HTMLSelectElement).value)"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
              >
                <option value="">请选择...</option>
                <option value="理性分析型，遇事先冷静思考">理性分析型</option>
                <option value="直觉感受型，跟着感觉走">直觉感受型</option>
                <option value="乐观主义者，总能看到希望">乐观主义者</option>
                <option value="悲观主义者，习惯做最坏打算">悲观主义者</option>
                <option value="全局思考型，喜欢从大局出发">全局思考型</option>
                <option value="细节关注型，注重每个细节">细节关注型</option>
              </select>
            </div>

            <!-- 决策方式 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                决策方式
                <span class="text-xs text-text-muted font-normal ml-1">如何做出选择</span>
              </label>
              <select 
                v-model="getDNAProfile(character).decision_style"
                @change="updateDNA(character, 'decision_style', ($event.target as HTMLSelectElement).value)"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
              >
                <option value="">请选择...</option>
                <option value="快速决断，不喜欢犹豫">快速决断型</option>
                <option value="反复权衡，考虑各种可能">深思熟虑型</option>
                <option value="依赖逻辑，用数据说话">逻辑驱动型</option>
                <option value="依赖情感，跟着心走">情感驱动型</option>
                <option value="喜欢独立决策，不爱听别人意见">独立决策型</option>
                <option value="喜欢征求他人意见再做决定">群策群力型</option>
              </select>
            </div>

            <!-- 隐藏的秘密 -->
            <div>
              <label class="block text-sm font-medium text-purple-700 mb-1">
                隐藏的秘密
                <span class="text-xs text-text-muted font-normal ml-1">不愿让人知道的事</span>
              </label>
              <textarea 
                v-model="getDNAProfile(character).hidden_secret"
                @input="updateDNA(character, 'hidden_secret', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：曾经因为自己的失误导致好友受伤，一直心怀愧疚"
                class="w-full p-2 border border-purple-200 rounded-md focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition bg-white text-sm"
                rows="2"
              ></textarea>
            </div>
          </div>

          <!-- DNA完成度提示 -->
          <div class="mt-4 flex items-center gap-2">
            <div class="flex-1 bg-bg-highlight rounded-full h-2">
              <div 
                class="bg-purple-500 h-2 rounded-full transition-all duration-300"
                :style="{ width: getDNACompleteness(character) + '%' }"
              ></div>
            </div>
            <span class="text-xs text-text-muted">{{ getDNACompleteness(character) }}% 完成</span>
          </div>
          <p class="mt-2 text-xs text-text-muted">
            💡 提示：DNA档案越完整，AI生成的角色行为和对话就越真实立体
          </p>
        </div>
      </transition>
    </div>
    
    <button @click="addCharacter" class="w-full mt-4 px-4 py-2 text-sm font-medium text-primary bg-primary-muted border border-indigo-200 rounded-md hover:bg-primary-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary/10">
      + 添加新角色
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, reactive, nextTick } from 'vue';
import { NovelAPI } from '@/api/novel';

interface DNAProfile {
  childhood_trauma: string;
  core_fear: string;
  inner_desire: string;
  speech_habits: string;
  body_language: string;
  thinking_pattern: string;
  decision_style: string;
  hidden_secret: string;
}

interface Character {
  name: string;
  identity: string;
  personality: string;
  goals: string;
  abilities: string;
  relationship_to_protagonist: string;
  power_system_id?: number | null;
  current_power_level_id?: number | null;
  extra?: {
    dna_profile?: DNAProfile;
    [key: string]: any;
  };
}

const props = defineProps({
  modelValue: {
    type: Array as () => Character[],
    default: () => []
  },
  projectId: {
    type: String,
    default: ''
  },
  powerSystems: {
    type: Array as () => Array<{ id: number, name: string, levels: Array<{ id: number, name: string }> }>,
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const localCharacters = ref<Character[]>([]);
const expandedDNA = reactive<Record<number, boolean>>({});
let syncing = false;

// 初始化DNA档案
const initDNAProfile = (): DNAProfile => ({
  childhood_trauma: '',
  core_fear: '',
  inner_desire: '',
  speech_habits: '',
  body_language: '',
  thinking_pattern: '',
  decision_style: '',
  hidden_secret: ''
});

// 获取角色的DNA档案
const getDNAProfile = (character: Character): DNAProfile => {
  if (!character.extra) {
    character.extra = {};
  }
  if (!character.extra.dna_profile) {
    character.extra.dna_profile = initDNAProfile();
  }
  return character.extra.dna_profile;
};

// 更新DNA字段
const updateDNA = (character: Character, field: keyof DNAProfile, value: string) => {
  const profile = getDNAProfile(character);
  profile[field] = value;
  // 触发更新
  emit('update:modelValue', JSON.parse(JSON.stringify(localCharacters.value)));
};

// 计算DNA完成度
const getDNACompleteness = (character: Character): number => {
  const profile = getDNAProfile(character);
  const fields = Object.values(profile);
  const filledFields = fields.filter(v => v && v.trim().length > 0);
  return Math.round((filledFields.length / fields.length) * 100);
};

// 切换DNA展开状态
const toggleDNA = (index: number) => {
  expandedDNA[index] = !expandedDNA[index];
};

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localCharacters.value = JSON.parse(JSON.stringify(newVal || []));
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localCharacters, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', JSON.parse(JSON.stringify(newVal)));
}, { deep: true });

const addCharacter = () => {
  localCharacters.value.push({ 
    name: '', 
    identity: '', 
    personality: '', 
    goals: '', 
    abilities: '', 
    relationship_to_protagonist: '',
    extra: {
      dna_profile: initDNAProfile()
    }
  });
};

const removeCharacter = (index: number) => {
  localCharacters.value.splice(index, 1);
  delete expandedDNA[index];
};

// DNA 自动推演
const isGeneratingDNA = ref(false);
const dnaMessage = ref('');
const dnaMessageType = ref<'success' | 'error' | 'info'>('info');

// 从章节同步角色
const isSyncing = ref(false);

const showDNAMessage = (msg: string, type: 'success' | 'error' | 'info' = 'info') => {
  dnaMessage.value = msg;
  dnaMessageType.value = type;
  setTimeout(() => { dnaMessage.value = ''; }, 5000);
};

const generateAllDNA = async (overwrite: boolean = false) => {
  if (!props.projectId || isGeneratingDNA.value) return;
  isGeneratingDNA.value = true;
  dnaMessage.value = '';
  try {
    const result = await NovelAPI.generateCharacterDNA(props.projectId, undefined, overwrite);
    if (result.status === 'skipped') {
      showDNAMessage(result.message, 'info');
    } else {
      showDNAMessage(result.message, 'success');
      // 重新加载角色数据以获取更新后的DNA
      await refreshCharacters();
    }
  } catch (error: any) {
    showDNAMessage(error.message || 'DNA推演失败，请重试', 'error');
  } finally {
    isGeneratingDNA.value = false;
  }
};

const generateSingleDNA = async (characterName: string) => {
  if (!props.projectId || isGeneratingDNA.value) return;
  isGeneratingDNA.value = true;
  dnaMessage.value = '';
  try {
    const result = await NovelAPI.generateCharacterDNA(props.projectId, [characterName], true);
    if (result.status === 'skipped') {
      showDNAMessage(result.message, 'info');
    } else {
      showDNAMessage(`已为 ${characterName} 生成DNA档案`, 'success');
      await refreshCharacters();
    }
  } catch (error: any) {
    showDNAMessage(error.message || 'DNA推演失败，请重试', 'error');
  } finally {
    isGeneratingDNA.value = false;
  }
};

const refreshCharacters = async () => {
  if (!props.projectId) return;
  try {
    const sectionData = await NovelAPI.getSection(props.projectId, 'characters');
    const updatedCharacters = sectionData.data?.characters || [];
    syncing = true;
    localCharacters.value = JSON.parse(JSON.stringify(updatedCharacters));
    nextTick(() => { syncing = false; });
    // 展开所有有DNA的角色面板
    updatedCharacters.forEach((char: any, idx: number) => {
      if (char?.extra?.dna_profile) {
        const profile = char.extra.dna_profile;
        const hasContent = Object.values(profile).some((v: any) => v && String(v).trim());
        if (hasContent) expandedDNA[idx] = true;
      }
    });
    emit('update:modelValue', JSON.parse(JSON.stringify(localCharacters.value)));
  } catch (error) {
    console.error('刷新角色数据失败:', error);
  }
};

const syncFromChapters = async () => {
  if (!props.projectId || isSyncing.value) return;
  isSyncing.value = true;
  dnaMessage.value = '';
  try {
    const result = await NovelAPI.syncCharactersFromChapters(props.projectId);
    if (result.status === 'no_new_characters') {
      showDNAMessage(result.message, 'info');
    } else {
      showDNAMessage(result.message, 'success');
      await refreshCharacters();
    }
  } catch (error: any) {
    showDNAMessage(error.message || '同步角色失败，请重试', 'error');
  } finally {
    isSyncing.value = false;
  }
};
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  overflow: hidden;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 1000px;
}
</style>
