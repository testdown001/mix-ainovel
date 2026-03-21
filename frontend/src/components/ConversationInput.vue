<!-- AIMETA P=对话输入_用户输入组件|R=输入框_发送|NR=不含消息展示|E=component:ConversationInput|X=internal|A=输入组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="fade-in">
    <!-- 加载状态 -->
    <div v-if="loading || !uiControl" class="flex justify-center items-center p-4">
      <div class="loader"></div>
    </div>

    <!-- 单选题 -->
    <div v-else-if="uiControl.type === 'single_choice'">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <button
          v-for="option in uiControl.options"
          :key="option.id"
          @click="handleOptionSelect(option.id, option.label)"
          class="choice-btn"
        >
          {{ option.label }}
        </button>
        <button
          @click="isManualInput = true"
          class="choice-btn-secondary"
        >
          我要输入
        </button>
      </div>
      <form @submit.prevent="handleTextSubmit" class="flex items-center gap-3">
        <textarea
          v-model="textInput"
          :placeholder="isManualInput ? '请输入您的想法...' : '选择上方选项或点击「我要输入」'"
          class="conv-textarea"
          :disabled="!isManualInput"
          rows="5"
          ref="textInputRef"
          @input="handleTextareaInput"
        ></textarea>
        <button
          type="submit"
          class="send-btn"
          :disabled="!isManualInput"
          :style="{ opacity: !isManualInput ? 0.4 : 1 }"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>

    <!-- 文本输入 -->
    <form v-else-if="uiControl.type === 'text_input'" @submit.prevent="handleTextSubmit" class="flex items-center gap-3">
      <textarea
        v-model="textInput"
        :placeholder="uiControl.placeholder || '请输入...'"
        class="conv-textarea"
        required
        ref="textInputRef"
        rows="5"
        @input="handleTextareaInput"
      ></textarea>
      <button type="submit" class="send-btn">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import type { UIControl } from '@/api/novel'

interface Props {
  uiControl: UIControl | null
  loading: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  submit: [userInput: { id: string; value: string } | null]
}>()

const textInput = ref('')
const textInputRef = ref<HTMLTextAreaElement>()
const isManualInput = ref(false)

const MIN_ROWS = 5
const MAX_ROWS = 5

const adjustTextareaHeight = () => {
  const textarea = textInputRef.value
  if (!textarea) return
  if (typeof window === 'undefined') return

  const lineHeight = parseFloat(window.getComputedStyle(textarea).lineHeight || '0') || 20
  const minHeight = lineHeight * MIN_ROWS
  const maxHeight = lineHeight * MAX_ROWS

  textarea.style.height = 'auto'
  const targetHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight))
  textarea.style.height = `${targetHeight}px`
}

const handleTextareaInput = () => {
  adjustTextareaHeight()
}

const handleOptionSelect = (id: string, label: string) => {
  emit('submit', { id, value: label })
}

const handleTextSubmit = () => {
  if (textInput.value.trim()) {
    emit('submit', { id: 'text_input', value: textInput.value.trim() })
    textInput.value = ''
    nextTick(() => adjustTextareaHeight())
  }
}

watch(
  () => props.uiControl,
  async (newControl) => {
    isManualInput.value = false
    textInput.value = ''

    await nextTick()
    adjustTextareaHeight()

    if (newControl?.type === 'text_input') {
      textInputRef.value?.focus()
    }
  },
  { deep: true }
)

watch(isManualInput, async (newValue) => {
  if (newValue) {
    await nextTick()
    adjustTextareaHeight()
    textInputRef.value?.focus()
  }
})
</script>

<style scoped>
.choice-btn {
  padding: 10px 12px;
  background: #1C1C1C;
  color: #FFE500;
  border: 1px solid #FFE50033;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}

.choice-btn:hover {
  background: #FFE50011;
  border-color: #FFE50066;
}

.choice-btn-secondary {
  padding: 10px 12px;
  background: #1C1C1C;
  color: #888;
  border: 1px solid #2A2A2A;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}

.choice-btn-secondary:hover {
  background: #2A2A2A;
  color: #fff;
}

.conv-textarea {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #2A2A2A;
  border-radius: 14px;
  background: #1C1C1C;
  color: #fff;
  font-size: 14px;
  outline: none;
  resize: none;
  overflow-y: auto;
  line-height: 1.6;
  transition: border-color 0.15s;
}

.conv-textarea:focus {
  border-color: #FFE500;
  box-shadow: 0 0 0 2px rgba(255, 229, 0, 0.1);
}

.conv-textarea:disabled {
  background: #141414;
  color: #555;
  cursor: not-allowed;
}

.conv-textarea::placeholder {
  color: #555;
}

.send-btn {
  flex-shrink: 0;
  width: 46px;
  height: 46px;
  background: #FFE500;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #000;
  transition: opacity 0.15s, transform 0.15s;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.send-btn:disabled {
  cursor: not-allowed;
}
</style>
