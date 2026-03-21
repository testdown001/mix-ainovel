<!-- AIMETA P=势力编辑器_势力信息编辑|R=势力CRUD|NR=不含角色编辑|E=component:FactionsEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-3 max-h-96 overflow-y-auto p-1">
    <div
      v-for="(faction, index) in localFactions"
      :key="index"
      class="relative p-4 border border-[#2A2A2A] rounded-xl bg-[#1C1C1C]"
    >
      <button
        @click="removeFaction(index)"
        class="absolute top-3 right-3 text-[#555] hover:text-[#FF4757] transition-colors p-1 rounded-lg hover:bg-[#FF4757]/10"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>
      <div class="mb-3 pr-8">
        <label class="block text-xs font-medium text-[#888] mb-1.5">阵营名称</label>
        <input
          type="text"
          v-model="faction.name"
          class="w-full px-0 py-1 border-b border-[#2A2A2A] focus:border-[#FFE500] outline-none transition-colors bg-transparent text-white text-sm placeholder-[#444]"
          placeholder="例如：幽灵侦探林远"
        />
      </div>
      <div>
        <label class="block text-xs font-medium text-[#888] mb-1.5">描述</label>
        <textarea
          v-model="faction.description"
          class="w-full h-20 px-3 py-2 mt-0.5 border border-[#2A2A2A] rounded-lg bg-[#141414] focus:border-[#FFE500] outline-none transition-colors text-sm text-[#CCCCCC] placeholder-[#444] resize-none"
          placeholder="关于这个阵营的详细描述..."
        ></textarea>
      </div>
    </div>
    <button
      @click="addFaction"
      class="w-full mt-1 px-4 py-2.5 text-sm font-medium text-[#FFE500] bg-[#FFE500]/6 border border-[#FFE500]/20 rounded-xl hover:bg-[#FFE500]/12 hover:border-[#FFE500]/40 transition-all focus:outline-none"
    >
      + 添加新阵营
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

interface Faction {
  name: string;
  description: string;
}

const props = defineProps({
  modelValue: {
    type: Array as () => Faction[],
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const localFactions = ref<Faction[]>([]);
let syncing = false;

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localFactions.value = JSON.parse(JSON.stringify(newVal || []));
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localFactions, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', JSON.parse(JSON.stringify(newVal)));
}, { deep: true });

const addFaction = () => {
  localFactions.value.push({ name: '', description: '' });
};

const removeFaction = (index: number) => {
  localFactions.value.splice(index, 1);
};
</script>
