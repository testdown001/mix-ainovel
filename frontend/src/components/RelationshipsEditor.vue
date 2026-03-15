<!-- AIMETA P=关系编辑器_角色关系编辑|R=关系CRUD|NR=不含角色编辑|E=component:RelationshipsEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-4 max-h-[600px] overflow-y-auto p-1">
    <!-- 从章节同步关系按钮 -->
    <div v-if="projectId" class="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-200">
      <div class="flex items-center gap-2">
        <span class="text-blue-600 text-lg">🔄</span>
        <span class="text-sm text-blue-700 font-medium">从章节同步关系</span>
        <span class="text-xs text-gray-500">从已生成章节中提取人物关系</span>
      </div>
      <button
        @click="syncFromChapters"
        :disabled="isSyncing"
        class="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
      >
        <svg v-if="isSyncing" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>{{ isSyncing ? '同步中...' : '同步关系' }}</span>
      </button>
    </div>
    <!-- 同步状态提示 -->
    <div v-if="syncMessage" class="p-3 rounded-lg text-sm" :class="syncMessageType === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : syncMessageType === 'error' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-blue-50 text-blue-700 border border-blue-200'">
      {{ syncMessage }}
    </div>

    <div v-for="(relationship, index) in localRelationships" :key="index" class="p-4 border border-gray-200 rounded-lg bg-gray-50 relative">
      <button @click="removeRelationship(index)" class="absolute top-2 right-2 text-red-400 hover:text-red-600 transition-colors p-1">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-2">
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">从</label>
          <input type="text" v-model="relationship.character_from" class="w-full p-1 border-b-2 border-gray-300 focus:border-indigo-500 outline-none transition bg-transparent" placeholder="例如：林远" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">到</label>
          <input type="text" v-model="relationship.character_to" class="w-full p-1 border-b-2 border-gray-300 focus:border-indigo-500 outline-none transition bg-transparent" placeholder="例如：苏晴" />
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-600 mb-1">关系描述</label>
        <textarea
          v-model="relationship.description"
          class="w-full h-20 p-2 mt-1 border border-gray-300 rounded-md focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition text-sm"
          placeholder="关于这段关系的详细描述..."
        ></textarea>
      </div>
    </div>
    <button @click="addRelationship" class="w-full mt-4 px-4 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-md hover:bg-indigo-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
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

// 从章节同步关系
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
