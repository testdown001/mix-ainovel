<!-- AIMETA P=数组输入组件|R=标签输入_以回车分割|E=component:ArrayInput|X=ui|A=输入组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="relative">
    <div class="flex flex-wrap gap-1.5 mb-2" v-if="localList.length > 0">
      <span
        v-for="(item, index) in localList"
        :key="index"
        class="inline-flex items-center gap-1 px-2.5 py-1 bg-[#2A2A2A] border border-[#333] text-[#CCCCCC] text-xs rounded-full"
      >
        {{ item }}
        <button
          type="button"
          @click="removeItem(index)"
          class="text-[#555] hover:text-[#FF4757] transition-colors"
        >
          <svg class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </span>
    </div>
    <input
      type="text"
      v-model="inputValue"
      @keydown.enter.prevent="handleEnter"
      @compositionstart="isComposing = true"
      @compositionend="isComposing = false"
      @blur="addItem"
      :placeholder="placeholder"
      class="block w-full rounded-xl border border-[#2A2A2A] bg-[#0A0A0A] focus:border-[#FFE500] outline-none transition-colors text-sm px-3 py-2 text-white placeholder-[#444]"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string[]
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const localList = ref<string[]>([...props.modelValue || []])
const inputValue = ref('')
const isComposing = ref(false)

watch(() => props.modelValue, (newVal) => {
  localList.value = [...(newVal || [])]
}, { deep: true })

const addItem = () => {
  const val = inputValue.value.trim()
  if (val && !localList.value.includes(val)) {
    localList.value.push(val)
    emit('update:modelValue', [...localList.value])
    inputValue.value = ''
  }
}

const handleEnter = (event: KeyboardEvent) => {
  if (isComposing.value || event.isComposing) return
  addItem()
}

const removeItem = (index: number) => {
  localList.value.splice(index, 1)
  emit('update:modelValue', [...localList.value])
}
</script>
