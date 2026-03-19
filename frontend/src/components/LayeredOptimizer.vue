<!-- AIMETA P=分层优化器_内容优化界面|R=优化建议展示|NR=不含内容修改|E=component:LayeredOptimizer|X=internal|A=优化器|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="layered-optimizer">
    <!-- 标题 -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-text-primary flex items-center gap-2">
        <span>✨ 分层优化</span>
        <span class="text-xs font-normal text-text-muted">(选择一个维度深度优化)</span>
      </h3>
    </div>

    <!-- 优化维度选择 -->
    <div class="grid grid-cols-2 gap-3 mb-4">
      <button
        v-for="dimension in dimensions"
        :key="dimension.id"
        @click="selectDimension(dimension.id)"
        :class="[
          'p-4 rounded-lg border-2 transition-all text-left',
          selectedDimension === dimension.id
            ? 'border-primary bg-primary-muted'
            : 'border-border bg-bg-surface hover:border-indigo-300 hover:bg-[rgba(255,255,255,0.05)]'
        ]"
      >
        <div class="flex items-center gap-2 mb-2">
          <span class="text-2xl">{{ dimension.icon }}</span>
          <span class="font-medium text-text-primary">{{ dimension.name }}</span>
        </div>
        <p class="text-xs text-text-muted">{{ dimension.description }}</p>
      </button>
    </div>

    <!-- 优化说明 -->
    <div v-if="selectedDimension" class="mb-4 p-4 bg-primary-muted rounded-lg border border-blue-200">
      <h4 class="font-medium text-blue-800 mb-2">{{ currentDimension?.name }}优化要点</h4>
      <ul class="text-sm text-primary space-y-1">
        <li v-for="(point, index) in currentDimension?.points" :key="index" class="flex items-start gap-2">
          <span class="text-blue-400">•</span>
          <span>{{ point }}</span>
        </li>
      </ul>
    </div>

    <!-- 额外指令 -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-text-secondary mb-2">额外优化指令 (可选)</label>
      <textarea
        v-model="additionalNotes"
        placeholder="例如：加强主角与反派的对话张力，突出两人之间的心理博弈"
        class="w-full p-3 border border-border rounded-lg focus:ring-2 focus:ring-primary/10 focus:border-border-focus outline-none transition text-sm"
        rows="3"
      ></textarea>
    </div>

    <!-- 操作按钮 -->
    <div class="flex gap-3">
      <button
        @click="startOptimization"
        :disabled="!selectedDimension || isOptimizing"
        :class="[
          'flex-1 py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2',
          selectedDimension && !isOptimizing
            ? 'bg-primary text-on-primary hover:bg-primary-hover'
            : 'bg-bg-highlight text-text-muted cursor-not-allowed'
        ]"
      >
        <svg v-if="isOptimizing" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>{{ isOptimizing ? '优化中...' : '开始优化' }}</span>
      </button>
      <button
        @click="$emit('cancel')"
        class="px-6 py-3 rounded-lg font-medium border border-border text-text-secondary hover:bg-[rgba(255,255,255,0.05)] transition-all"
      >
        取消
      </button>
    </div>

    <!-- 优化历史 -->
    <div v-if="optimizationHistory.length > 0" class="mt-6 pt-4 border-t border-border">
      <h4 class="text-sm font-medium text-text-secondary mb-3">优化历史</h4>
      <div class="space-y-2">
        <div
          v-for="(record, index) in optimizationHistory"
          :key="index"
          class="flex items-center justify-between p-3 bg-bg-elevated rounded-lg"
        >
          <div class="flex items-center gap-2">
            <span>{{ getDimensionIcon(record.dimension) }}</span>
            <span class="text-sm text-text-secondary">{{ getDimensionName(record.dimension) }}</span>
            <span class="text-xs text-text-muted">{{ record.timestamp }}</span>
          </div>
          <button
            @click="$emit('revert', record)"
            class="text-xs text-primary hover:text-primary"
          >
            回退
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

interface Dimension {
  id: string;
  name: string;
  icon: string;
  description: string;
  points: string[];
}

interface OptimizationRecord {
  dimension: string;
  timestamp: string;
  originalContent: string;
}

const props = defineProps({
  chapterContent: {
    type: String,
    default: ''
  },
  optimizationHistory: {
    type: Array as () => OptimizationRecord[],
    default: () => []
  }
});

const emit = defineEmits(['optimize', 'cancel', 'revert']);

const selectedDimension = ref<string | null>(null);
const additionalNotes = ref('');
const isOptimizing = ref(false);

const dimensions: Dimension[] = [
  {
    id: 'dialogue',
    name: '对话优化',
    icon: '💬',
    description: '让每句对话都有独特的声音和潜台词',
    points: [
      '每个角色都有独特的说话风格',
      '对话推动情节发展，不做无效交流',
      '潜台词丰富，言外之意明显',
      '情绪通过对话节奏体现'
    ]
  },
  {
    id: 'environment',
    name: '环境描写',
    icon: '🌄',
    description: '让场景氛围与情绪完美融合',
    points: [
      '场景氛围与情绪节拍匹配',
      '环境细节反映角色内心状态',
      '感官描写具体生动（视、听、嗅、触、味）',
      '环境变化暗示剧情走向'
    ]
  },
  {
    id: 'psychology',
    name: '心理活动',
    icon: '🧠',
    description: '深入角色内心，展现复杂情感',
    points: [
      '内心独白符合角色性格和DNA档案',
      '情感层次递进清晰',
      '心理冲突具体可感',
      '思维跳跃逻辑合理'
    ]
  },
  {
    id: 'rhythm',
    name: '节奏韵律',
    icon: '🎵',
    description: '优化文字节奏，增强阅读体验',
    points: [
      '长短句交替自然，有呼吸感',
      '重要情节放慢，日常情节加快',
      '段落长度变化有序',
      '标点符号使用恰当'
    ]
  }
];

const currentDimension = computed(() => {
  return dimensions.find(d => d.id === selectedDimension.value);
});

const selectDimension = (id: string) => {
  selectedDimension.value = selectedDimension.value === id ? null : id;
};

const getDimensionIcon = (id: string) => {
  return dimensions.find(d => d.id === id)?.icon || '📝';
};

const getDimensionName = (id: string) => {
  return dimensions.find(d => d.id === id)?.name || '未知';
};

const startOptimization = async () => {
  if (!selectedDimension.value) return;
  
  isOptimizing.value = true;
  
  emit('optimize', {
    dimension: selectedDimension.value,
    additionalNotes: additionalNotes.value,
    originalContent: props.chapterContent
  });
  
  // 实际优化逻辑由父组件处理
  // isOptimizing 状态由父组件在完成后重置
};

// 暴露方法给父组件
defineExpose({
  setOptimizing: (value: boolean) => {
    isOptimizing.value = value;
  },
  reset: () => {
    selectedDimension.value = null;
    additionalNotes.value = '';
    isOptimizing.value = false;
  }
});
</script>

<style scoped>
/* 动画效果 */
button {
  transform: translateY(0);
}

button:active:not(:disabled) {
  transform: translateY(1px);
}
</style>
