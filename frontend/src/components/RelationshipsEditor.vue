<!-- AIMETA P=关系编辑器_角色关系编辑|R=关系CRUD|NR=不含角色编辑|E=component:RelationshipsEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-3 max-h-[600px] overflow-y-auto p-1">
    <!-- 从章节同步关系 -->
    <div v-if="projectId" class="flex items-center justify-between px-4 py-3 bg-[#06B6D4]/8 rounded-xl border border-[#06B6D4]/20">
      <div class="flex items-center gap-2.5 min-w-0">
        <span class="text-[#06B6D4] text-base flex-shrink-0">🔄</span>
        <span class="text-sm text-[#06B6D4] font-medium flex-shrink-0">从章节同步关系</span>
        <span class="text-xs text-[#555] truncate">从已生成章节中提取人物关系</span>
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
        <span>{{ isSyncing ? '同步中...' : '同步关系' }}</span>
      </button>
    </div>

    <!-- 同步状态提示 -->
    <div
      v-if="syncMessage"
      class="px-4 py-2.5 rounded-lg text-sm border"
      :class="{
        'bg-[#2ED573]/8 text-[#2ED573] border-[#2ED573]/20': syncMessageType === 'success',
        'bg-[#FF4757]/8 text-[#FF4757] border-[#FF4757]/20': syncMessageType === 'error',
        'bg-[#06B6D4]/8 text-[#06B6D4] border-[#06B6D4]/20': syncMessageType === 'info',
      }"
    >
      {{ syncMessage }}
    </div>

    <!-- 关系列表 -->
    <div
      v-for="(relationship, index) in localRelationships"
      :key="index"
      class="relative p-4 border border-[#2A2A2A] rounded-xl bg-[#1C1C1C]"
    >
      <!-- 删除按钮 -->
      <button
        @click="removeRelationship(index)"
        class="absolute top-3 right-3 text-[#555] hover:text-[#FF4757] transition-colors p-1 rounded-lg hover:bg-[#FF4757]/10"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3 pr-8">
        <div>
          <label class="block text-xs font-medium text-[#888] mb-1.5">从</label>
          <input
            type="text"
            v-model="relationship.character_from"
            class="w-full px-0 py-1 border-b border-[#2A2A2A] focus:border-[#FFE500] outline-none transition-colors bg-transparent text-white text-sm placeholder-[#444]"
            placeholder="例如：林远"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-[#888] mb-1.5">到</label>
          <input
            type="text"
            v-model="relationship.character_to"
            class="w-full px-0 py-1 border-b border-[#2A2A2A] focus:border-[#FFE500] outline-none transition-colors bg-transparent text-white text-sm placeholder-[#444]"
            placeholder="例如：苏晴"
          />
        </div>
      </div>
      <div>
        <label class="block text-xs font-medium text-[#888] mb-1.5">关系描述</label>
        <textarea
          v-model="relationship.description"
          class="w-full h-20 px-3 py-2 mt-0.5 border border-[#2A2A2A] rounded-lg bg-[#141414] focus:border-[#FFE500] outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444] resize-none"
          placeholder="关于这段关系的详细描述..."
        ></textarea>
      </div>
    </div>

    <!-- 添加新关系 -->
    <button
      @click="addRelationship"
      class="w-full mt-1 px-4 py-2.5 text-sm font-medium text-[#FFE500] bg-[#FFE500]/6 border border-[#FFE500]/20 rounded-xl hover:bg-[#FFE500]/12 hover:border-[#FFE500]/40 transition-all focus:outline-none"
    >
      + 添加新关系
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { NovelAPI } from '@/api/novel';

interface Relationship {
  character_from: string;
  character_to: string;
  description: string;
}

const props = defineProps({
  modelValue: {
    type: Array as () => Relationship[],
    default: () => []
  },
  projectId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue']);

const localRelationships = ref<Relationship[]>([]);
let syncing = false;

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localRelationships.value = JSON.parse(JSON.stringify(newVal || []));
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localRelationships, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', JSON.parse(JSON.stringify(newVal)));
}, { deep: true });

const addRelationship = () => {
  localRelationships.value.push({
    character_from: '',
    character_to: '',
    description: ''
  });
};

const removeRelationship = (index: number) => {
  localRelationships.value.splice(index, 1);
};

const isSyncing = ref(false);
const syncMessage = ref('');
const syncMessageType = ref<'success' | 'error' | 'info'>('info');

const showMessage = (msg: string, type: 'success' | 'error' | 'info' = 'info') => {
  syncMessage.value = msg;
  syncMessageType.value = type;
  setTimeout(() => { syncMessage.value = ''; }, 5000);
};

const syncFromChapters = async () => {
  if (!props.projectId || isSyncing.value) return;
  isSyncing.value = true;
  syncMessage.value = '';
  try {
    const result = await NovelAPI.syncRelationshipsFromChapters(props.projectId);
    if (result.status === 'no_new_relationships') {
      showMessage(result.message, 'info');
    } else {
      showMessage(result.message, 'success');
      await refreshRelationships();
    }
  } catch (error: any) {
    showMessage(error.message || '同步关系失败，请重试', 'error');
  } finally {
    isSyncing.value = false;
  }
};

const refreshRelationships = async () => {
  if (!props.projectId) return;
  try {
    const sectionData = await NovelAPI.getSection(props.projectId, 'relationships');
    const updated = sectionData.data?.relationships || [];
    syncing = true;
    localRelationships.value = JSON.parse(JSON.stringify(updated));
    nextTick(() => { syncing = false; });
    emit('update:modelValue', JSON.parse(JSON.stringify(localRelationships.value)));
  } catch (error) {
    console.error('刷新关系数据失败:', error);
  }
};
</script>
