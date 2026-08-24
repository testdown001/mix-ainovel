<!-- AIMETA P=批量生成正文弹窗_顺序生成配置|R=生成数量_统一写作指令|NR=不含生成逻辑|E=component:WDBatchGenerateModal|X=ui|A=批量正文弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <TransitionRoot as="template" :show="show">
    <Dialog as="div" class="relative z-50" @close="$emit('close')">
      <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0" style="background-color: rgba(0, 0, 0, 0.32);" />
      </TransitionChild>

      <div class="fixed inset-0 z-10 overflow-y-auto">
        <div class="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
          <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95" enter-to="opacity-100 translate-y-0 sm:scale-100" leave="ease-in duration-200" leave-from="opacity-100 translate-y-0 sm:scale-100" leave-to="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95">
            <DialogPanel class="md-dialog m3-outline-dialog text-left transition-all sm:my-6 sm:w-full sm:max-w-lg">
              <div class="px-5 pt-6 pb-5 sm:px-6 sm:pt-6 sm:pb-5">
                <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
                  <div class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full sm:mx-0 sm:h-12 sm:w-12" style="background-color: var(--md-primary-container);">
                    <svg class="h-6 w-6" style="color: var(--md-on-primary-container);" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                    </svg>
                  </div>
                  <div class="text-center sm:flex-1 sm:text-left">
                    <DialogTitle as="h3" class="md-headline-small font-semibold leading-7">批量生成正文</DialogTitle>
                    <div class="mt-2">
                      <p class="md-body-medium md-on-surface-variant">系统将从首个未完成章节开始，按故事顺序生成并自动选版。</p>
                    </div>
                  </div>
                </div>

                <div class="mt-6">
                  <label class="md-text-field-label">起始章节</label>
                  <div class="mt-2 md-body-medium p-3 rounded-lg" style="background-color: var(--md-surface-container); color: var(--md-on-surface-variant);">
                    第 {{ startChapter }} 章
                  </div>
                </div>

                <div class="mt-5">
                  <label for="batchCount" class="md-text-field-label">生成章节数</label>
                  <input type="number" name="batchCount" id="batchCount" v-model.number="count" class="md-text-field-input w-full mt-2" min="1" :max="maxCount">
                  <div class="mt-3 flex flex-wrap justify-center gap-3">
                    <button v-for="preset in countPresets" :key="preset" @click="count = Math.min(preset, maxCount)"
                      :class="['md-btn md-btn-outlined md-ripple', count === Math.min(preset, maxCount) ? 'm3-count-selected' : '']">
                      {{ preset }} 章
                    </button>
                  </div>
                  <p v-if="maxCount > 0" class="mt-2 md-body-small md-on-surface-variant" style="text-align: center;">
                    可生成范围：第 {{ startChapter }} ~ {{ startChapter + count - 1 }} 章（最多 {{ maxCount }} 章有大纲）
                  </p>
                  <p v-else class="mt-2 md-body-small" style="color: var(--md-error); text-align: center;">
                    没有可生成的章节，请先生成大纲。
                  </p>
                </div>

                <div class="mt-5">
                  <label for="batchWritingNotes" class="md-text-field-label">写作指令 <span class="md-on-surface-variant" style="font-weight: normal;">（可选，适用于所有章节）</span></label>
                  <textarea name="batchWritingNotes" id="batchWritingNotes" v-model="writingNotes" class="md-text-field-input w-full mt-2" rows="3" placeholder="例如：注意保持悬疑氛围，适当加入环境描写..."></textarea>
                </div>
              </div>
              <div class="px-6 py-4 sm:flex sm:flex-row-reverse sm:px-8" style="background-color: var(--md-surface-container-low);">
                <button type="button" class="md-btn md-btn-filled md-ripple sm:ml-3 sm:w-auto w-full justify-center" :disabled="count < 1 || maxCount < 1" @click="handleStart">开始批量生成</button>
                <button type="button" class="md-btn md-btn-outlined md-ripple sm:mt-0 sm:ml-3 sm:w-auto w-full justify-center mt-3" @click="$emit('close')">取消</button>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'

interface Props {
  show: boolean
  startChapter: number
  maxCount: number
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  start: [count: number, writingNotes?: string]
}>()

const count = ref(3)
const writingNotes = ref('')
const countPresets = [3, 5, 10, 20]

// 弹窗打开时重置状态
watch(() => props.show, (val) => {
  if (val) {
    count.value = Math.min(3, props.maxCount)
    writingNotes.value = ''
  }
})

// 确保 count 不超过 maxCount
watch(() => props.maxCount, (val) => {
  if (count.value > val) count.value = val
})

const handleStart = () => {
  if (count.value > 0 && props.maxCount > 0) {
    emit('start', count.value, writingNotes.value || undefined)
    emit('close')
  }
}
</script>

<style scoped>
.m3-outline-dialog {
  border-radius: var(--md-radius-xl);
}

.m3-count-selected {
  background-color: var(--md-primary);
  color: var(--md-on-primary);
  border-color: transparent;
}
</style>
