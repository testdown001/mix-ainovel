<!-- AIMETA P=增强角色编辑器_增强版角色编辑|R=增强角色编辑|NR=不含基础功能|E=component:CharactersEditorEnhanced|X=internal|A=增强编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-3 max-h-[600px] overflow-y-auto p-1">
    <!-- 从章节同步角色 -->
    <div v-if="projectId" class="flex items-center justify-between px-4 py-3 bg-[#06B6D4]/8 rounded-xl border border-[#06B6D4]/20">
      <div class="flex items-center gap-2.5 min-w-0">
        <span class="text-[#06B6D4] text-base flex-shrink-0">🔄</span>
        <span class="text-sm text-[#06B6D4] font-medium flex-shrink-0">从章节同步角色</span>
        <span class="text-xs text-[#555] truncate">从已生成章节中提取新增人物</span>
      </div>
      <button
        @click="syncFromChapters"
        :disabled="isSyncing"
        class="ml-3 px-4 py-1.5 text-sm font-semibold text-black bg-[#06B6D4] rounded-lg hover:bg-[#0891B2] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 flex-shrink-0"
      >
        <svg v-if="isSyncing" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>{{ isSyncing ? '同步中...' : '同步角色' }}</span>
      </button>
    </div>

    <!-- 批量生成DNA -->
    <div v-if="projectId" class="flex items-center justify-between px-4 py-3 bg-[#A855F7]/8 rounded-xl border border-[#A855F7]/20">
      <div class="flex items-center gap-2.5 min-w-0">
        <span class="text-[#A855F7] text-base flex-shrink-0">🧬</span>
        <span class="text-sm text-[#A855F7] font-medium flex-shrink-0">角色DNA档案</span>
        <span class="text-xs text-[#555] truncate">基于大纲和剧情自动推演角色心理档案</span>
      </div>
      <button
        @click="generateAllDNA(false)"
        :disabled="isGeneratingDNA"
        class="ml-3 px-4 py-1.5 text-sm font-semibold text-white bg-[#A855F7] rounded-lg hover:bg-[#9333EA] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 flex-shrink-0"
      >
        <svg v-if="isGeneratingDNA" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>{{ isGeneratingDNA ? '推演中...' : '一键生成全部DNA' }}</span>
      </button>
    </div>

    <!-- DNA / 同步状态提示 -->
    <div
      v-if="dnaMessage"
      class="px-4 py-2.5 rounded-lg text-sm border"
      :class="{
        'bg-[#2ED573]/8 text-[#2ED573] border-[#2ED573]/20': dnaMessageType === 'success',
        'bg-[#FF4757]/8 text-[#FF4757] border-[#FF4757]/20': dnaMessageType === 'error',
        'bg-[#06B6D4]/8 text-[#06B6D4] border-[#06B6D4]/20': dnaMessageType === 'info',
      }"
    >
      {{ dnaMessage }}
    </div>

    <!-- 角色列表 -->
    <div
      v-for="(character, index) in localCharacters"
      :key="index"
      class="border border-[#2A2A2A] rounded-xl bg-[#1C1C1C] relative"
    >
      <!-- 删除按钮 -->
      <button
        @click="removeCharacter(index)"
        class="absolute top-3 right-3 text-[#555] hover:text-[#FF4757] transition-colors p-1 rounded-lg hover:bg-[#FF4757]/10 z-10"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>

      <!-- 基础信息 -->
      <div class="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 pr-10">
        <div v-for="field in [
          { key: 'name', label: '姓名' },
          { key: 'identity', label: '身份' },
          { key: 'personality', label: '性格' },
          { key: 'goals', label: '目标' },
          { key: 'abilities', label: '能力' },
          { key: 'relationship_to_protagonist', label: '与主角关系' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-[#888] mb-1.5">{{ field.label }}</label>
          <input
            type="text"
            v-model="(character as any)[field.key]"
            class="w-full px-0 py-1 border-b border-[#2A2A2A] focus:border-[#FFE500] outline-none transition-colors bg-transparent text-white text-sm placeholder-[#444]"
          />
        </div>

        <!-- 力量体系 -->
        <div>
          <label class="block text-xs font-medium text-[#888] mb-1.5">力量体系</label>
          <select
            v-model="character.power_system_id"
            @change="character.current_power_level_id = null"
            class="w-full px-0 py-1 border-b border-[#2A2A2A] focus:border-[#FFE500] outline-none transition-colors bg-transparent text-white text-sm h-[34px]"
          >
            <option class="bg-[#1C1C1C]" :value="null">无</option>
            <option class="bg-[#1C1C1C]" v-for="ps in powerSystems" :key="ps.id" :value="ps.id">{{ ps.name }}</option>
          </select>
        </div>

        <!-- 当前境界 -->
        <div v-if="character.power_system_id">
          <label class="block text-xs font-medium text-[#888] mb-1.5">当前境界</label>
          <select
            v-model="character.current_power_level_id"
            class="w-full px-0 py-1 border-b border-[#2A2A2A] focus:border-[#FFE500] outline-none transition-colors bg-transparent text-white text-sm h-[34px]"
          >
            <option class="bg-[#1C1C1C]" :value="null">未知</option>
            <template v-if="powerSystems.find(ps => ps.id === character.power_system_id)">
              <option class="bg-[#1C1C1C]" v-for="lvl in powerSystems.find(ps => ps.id === character.power_system_id)?.levels || []" :key="lvl.id" :value="lvl.id">
                {{ lvl.name }}
              </option>
            </template>
          </select>
        </div>
      </div>

      <!-- DNA档案 toggle -->
      <div class="px-4 pb-3 border-t border-[#2A2A2A] pt-3 flex items-center justify-between">
        <button
          @click="toggleDNA(index)"
          class="flex items-center gap-2 text-sm font-medium text-[#A855F7] hover:text-[#C084FC] transition-colors"
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
          <span class="text-xs text-[#555]">(让角色更立体)</span>
        </button>
        <button
          v-if="projectId && character.name"
          @click.stop="generateSingleDNA(character.name)"
          :disabled="isGeneratingDNA"
          class="px-3 py-1 text-xs font-medium text-[#A855F7] bg-[#A855F7]/8 border border-[#A855F7]/20 rounded-lg hover:bg-[#A855F7]/15 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ isGeneratingDNA ? '推演中...' : 'AI推演' }}
        </button>
      </div>

      <!-- DNA档案内容 -->
      <transition name="slide">
        <div v-if="expandedDNA[index]" class="mx-4 mb-4 p-4 bg-[#A855F7]/5 rounded-xl border border-[#A855F7]/15">
          <div class="grid grid-cols-1 gap-4">
            <!-- 童年经历 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                童年经历/创伤
                <span class="text-[#555] font-normal ml-1">影响角色的防御机制和情感触发点</span>
              </label>
              <textarea
                v-model="getDNAProfile(character).childhood_trauma"
                @input="updateDNA(character, 'childhood_trauma', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：父母离异后由祖母抚养，从小学会察言观色，害怕被抛弃"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444] resize-none"
                rows="2"
              ></textarea>
            </div>
            <!-- 核心恐惧 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                核心恐惧
                <span class="text-[#555] font-normal ml-1">驱动角色行为的深层恐惧</span>
              </label>
              <input
                type="text"
                v-model="getDNAProfile(character).core_fear"
                @input="updateDNA(character, 'core_fear', ($event.target as HTMLInputElement).value)"
                placeholder="例如：害怕被抛弃、害怕失控、害怕不被爱"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444]"
              />
            </div>
            <!-- 内心渴望 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                内心渴望
                <span class="text-[#555] font-normal ml-1">角色真正想要的，可能连自己都不清楚</span>
              </label>
              <input
                type="text"
                v-model="getDNAProfile(character).inner_desire"
                @input="updateDNA(character, 'inner_desire', ($event.target as HTMLInputElement).value)"
                placeholder="例如：渴望被认可、渴望归属感、渴望证明自己"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444]"
              />
            </div>
            <!-- 说话习惯 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                说话习惯
                <span class="text-[#555] font-normal ml-1">口头禅、语气词、紧张时的变化</span>
              </label>
              <textarea
                v-model="getDNAProfile(character).speech_habits"
                @input="updateDNA(character, 'speech_habits', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：喜欢用反问句，紧张时语速加快，常说'怎么说呢...'"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444] resize-none"
                rows="2"
              ></textarea>
            </div>
            <!-- 身体语言 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                身体语言
                <span class="text-[#555] font-normal ml-1">紧张时的小动作、特有的姿态</span>
              </label>
              <textarea
                v-model="getDNAProfile(character).body_language"
                @input="updateDNA(character, 'body_language', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：紧张时会摸耳朵，思考时喜欢转笔，说谎时不敢直视对方"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444] resize-none"
                rows="2"
              ></textarea>
            </div>
            <!-- 思维模式 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                思维模式
                <span class="text-[#555] font-normal ml-1">理性/感性、乐观/悲观</span>
              </label>
              <select
                v-model="getDNAProfile(character).thinking_pattern"
                @change="updateDNA(character, 'thinking_pattern', ($event.target as HTMLSelectElement).value)"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC]"
              >
                <option class="bg-[#141414]" value="">请选择...</option>
                <option class="bg-[#141414]" value="理性分析型，遇事先冷静思考">理性分析型</option>
                <option class="bg-[#141414]" value="直觉感受型，跟着感觉走">直觉感受型</option>
                <option class="bg-[#141414]" value="乐观主义者，总能看到希望">乐观主义者</option>
                <option class="bg-[#141414]" value="悲观主义者，习惯做最坏打算">悲观主义者</option>
                <option class="bg-[#141414]" value="全局思考型，喜欢从大局出发">全局思考型</option>
                <option class="bg-[#141414]" value="细节关注型，注重每个细节">细节关注型</option>
              </select>
            </div>
            <!-- 决策方式 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                决策方式
                <span class="text-[#555] font-normal ml-1">如何做出选择</span>
              </label>
              <select
                v-model="getDNAProfile(character).decision_style"
                @change="updateDNA(character, 'decision_style', ($event.target as HTMLSelectElement).value)"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC]"
              >
                <option class="bg-[#141414]" value="">请选择...</option>
                <option class="bg-[#141414]" value="快速决断，不喜欢犹豫">快速决断型</option>
                <option class="bg-[#141414]" value="反复权衡，考虑各种可能">深思熟虑型</option>
                <option class="bg-[#141414]" value="依赖逻辑，用数据说话">逻辑驱动型</option>
                <option class="bg-[#141414]" value="依赖情感，跟着心走">情感驱动型</option>
                <option class="bg-[#141414]" value="喜欢独立决策，不爱听别人意见">独立决策型</option>
                <option class="bg-[#141414]" value="喜欢征求他人意见再做决定">群策群力型</option>
              </select>
            </div>
            <!-- 隐藏的秘密 -->
            <div>
              <label class="block text-xs font-medium text-[#A855F7] mb-1">
                隐藏的秘密
                <span class="text-[#555] font-normal ml-1">不愿让人知道的事</span>
              </label>
              <textarea
                v-model="getDNAProfile(character).hidden_secret"
                @input="updateDNA(character, 'hidden_secret', ($event.target as HTMLTextAreaElement).value)"
                placeholder="例如：曾经因为自己的失误导致好友受伤，一直心怀愧疚"
                class="w-full px-3 py-2 border border-[#A855F7]/20 rounded-lg bg-[#141414] focus:border-[#A855F7]/50 outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444] resize-none"
                rows="2"
              ></textarea>
            </div>
          </div>

          <!-- DNA完成度 -->
          <div class="mt-4 flex items-center gap-3">
            <div class="flex-1 bg-[#2A2A2A] rounded-full h-1.5">
              <div
                class="bg-[#A855F7] h-1.5 rounded-full transition-all duration-300"
                :style="{ width: getDNACompleteness(character) + '%' }"
              ></div>
            </div>
            <span class="text-xs text-[#555]">{{ getDNACompleteness(character) }}% 完成</span>
          </div>
          <p class="mt-2 text-xs text-[#555]">
            💡 DNA档案越完整，AI生成的角色行为和对话就越真实立体
          </p>
        </div>
      </transition>
    </div>

    <!-- 添加新角色 -->
    <button
      @click="addCharacter"
      class="w-full mt-1 px-4 py-2.5 text-sm font-medium text-[#FFE500] bg-[#FFE500]/6 border border-[#FFE500]/20 rounded-xl hover:bg-[#FFE500]/12 hover:border-[#FFE500]/40 transition-all focus:outline-none"
    >
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

const getDNAProfile = (character: Character): DNAProfile => {
  if (!character.extra) character.extra = {};
  if (!character.extra.dna_profile) character.extra.dna_profile = initDNAProfile();
  return character.extra.dna_profile;
};

const updateDNA = (character: Character, field: keyof DNAProfile, value: string) => {
  const profile = getDNAProfile(character);
  profile[field] = value;
  emit('update:modelValue', JSON.parse(JSON.stringify(localCharacters.value)));
};

const getDNACompleteness = (character: Character): number => {
  const profile = getDNAProfile(character);
  const fields = Object.values(profile);
  const filledFields = fields.filter(v => v && v.trim().length > 0);
  return Math.round((filledFields.length / fields.length) * 100);
};

const toggleDNA = (index: number) => {
  expandedDNA[index] = !expandedDNA[index];
};

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localCharacters.value = JSON.parse(JSON.stringify(newVal || []));
  nextTick(() => { syncing = false; });
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
    extra: { dna_profile: initDNAProfile() }
  });
};

const removeCharacter = (index: number) => {
  localCharacters.value.splice(index, 1);
  delete expandedDNA[index];
};

const isGeneratingDNA = ref(false);
const dnaMessage = ref('');
const dnaMessageType = ref<'success' | 'error' | 'info'>('info');
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
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 1000px;
}
</style>
