<!-- AIMETA P=章纲与可选正文生成弹窗|R=章纲表单_两阶段自动生成选择|NR=不含生成逻辑|E=component:WDGenerateOutlineModal|X=ui|A=生成弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <TransitionRoot as="template" :show="show">
    <Dialog as="div" class="relative z-50" @close="$emit('close')">
      <TransitionChild
        as="template"
        enter="ease-out duration-300"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-200"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0" style="background-color: rgba(0, 0, 0, 0.32)" />
      </TransitionChild>

      <div class="fixed inset-0 z-10 overflow-y-auto">
        <div
          class="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0"
        >
          <TransitionChild
            as="template"
            enter="ease-out duration-300"
            enter-from="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            enter-to="opacity-100 translate-y-0 sm:scale-100"
            leave="ease-in duration-200"
            leave-from="opacity-100 translate-y-0 sm:scale-100"
            leave-to="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
          >
            <DialogPanel
              class="md-dialog m3-outline-dialog text-left transition-all sm:my-6 sm:w-full sm:max-w-lg"
            >
              <div class="px-5 pt-6 pb-5 sm:px-6 sm:pt-6 sm:pb-5">
                <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
                  <div
                    class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full sm:mx-0 sm:h-12 sm:w-12"
                    style="background-color: var(--md-primary-container)"
                  >
                    <svg
                      class="h-6 w-6"
                      style="color: var(--md-on-primary-container)"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke-width="1.5"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
                    </svg>
                  </div>
                  <div class="text-center sm:flex-1 sm:text-left">
                    <DialogTitle as="h3" class="md-headline-small font-semibold leading-7"
                      >生成后续大纲</DialogTitle
                    >
                    <div class="mt-2">
                      <p class="md-body-medium md-on-surface-variant">
                        请输入或选择要生成的后续章节数量。
                      </p>
                    </div>
                  </div>
                </div>
                <div class="mt-6">
                  <label for="numChapters" class="md-text-field-label">本次生成数量</label>
                  <input
                    type="number"
                    name="numChapters"
                    id="numChapters"
                    v-model.number="numChapters"
                    class="md-text-field-input w-full mt-2"
                    min="1"
                    max="200"
                  />
                  <div class="mt-5 flex flex-wrap justify-center gap-3">
                    <button
                      v-for="count in [5, 10, 25, 50]"
                      :key="count"
                      @click="setNumChapters(count)"
                      :class="[
                        'md-btn md-btn-outlined md-ripple',
                        numChapters === count ? 'm3-count-selected' : '',
                      ]"
                    >
                      {{ count }} 章
                    </button>
                  </div>
                </div>
                <div class="mt-5">
                  <label for="estimatedTotal" class="md-text-field-label"
                    >预计总章节数
                    <span class="md-on-surface-variant" style="font-weight: normal"
                      >（可选，帮助AI控制故事节奏）</span
                    ></label
                  >
                  <input
                    type="number"
                    name="estimatedTotal"
                    id="estimatedTotal"
                    v-model.number="estimatedTotal"
                    class="md-text-field-input w-full mt-2"
                    min="0"
                    max="10000"
                    placeholder="如：200万字约667章"
                  />
                  <div class="mt-3 flex flex-wrap justify-center gap-3">
                    <button
                      v-for="preset in totalPresets"
                      :key="preset.value"
                      @click="estimatedTotal = preset.value"
                      :class="[
                        'md-btn md-btn-outlined md-ripple m3-preset-btn',
                        estimatedTotal === preset.value ? 'm3-count-selected' : '',
                      ]"
                    >
                      {{ preset.label }}
                    </button>
                  </div>
                  <p
                    v-if="estimatedTotal > 0"
                    class="mt-2 md-body-small md-on-surface-variant"
                    style="text-align: center"
                  >
                    ≈ {{ Math.round(estimatedTotal * 0.3) }}万字（按均3000字/章）
                  </p>
                </div>
                <div class="mt-5">
                  <label for="userPrompt" class="md-text-field-label"
                    >附加剧情提示
                    <span class="md-on-surface-variant" style="font-weight: normal"
                      >（可选，指定你想加入的剧情）</span
                    ></label
                  >
                  <textarea
                    name="userPrompt"
                    id="userPrompt"
                    v-model="userPrompt"
                    class="md-text-field-input w-full mt-2"
                    rows="3"
                    placeholder="例如：主角在这里会遇到一个神秘的白发老爷爷传授武功..."
                  ></textarea>
                </div>
                <label class="auto-body-option mt-5" :class="{ selected: generateChapters }">
                  <input v-model="generateChapters" type="checkbox" />
                  <span class="option-check" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                      <path d="m6 12.5 3.5 3.5L18 8" />
                    </svg>
                  </span>
                  <span>
                    <strong>同时生成对应章节正文</strong>
                    <small>
                      先完成章纲，再使用“{{
                        presetLabel
                      }}”逐章写作并自动确认最佳版本；正文生成会消耗积分。
                    </small>
                  </span>
                </label>
                <p v-if="autoBodyError" class="auto-body-error">{{ autoBodyError }}</p>
              </div>
              <div
                class="px-6 py-4 sm:flex sm:flex-row-reverse sm:px-8"
                style="background-color: var(--md-surface-container-low)"
              >
                <button
                  type="button"
                  class="md-btn md-btn-filled md-ripple sm:ml-3 sm:w-auto w-full justify-center"
                  :disabled="Boolean(autoBodyError)"
                  @click="handleGenerate"
                >
                  {{ generateChapters ? '生成章纲并写正文' : '生成章纲' }}
                </button>
                <button
                  type="button"
                  class="md-btn md-btn-outlined md-ripple sm:mt-0 sm:ml-3 sm:w-auto w-full justify-center mt-3"
                  @click="$emit('close')"
                >
                  取消
                </button>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'
import { useNovelStore } from '@/stores/novel'

interface Props {
  show: boolean
  selectedPreset?: string
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'generate'])

const novelStore = useNovelStore()

const numChapters = ref(25)
const estimatedTotal = ref(0)
const userPrompt = ref('')
const generateChapters = ref(false)
const presetLabel = computed(
  () =>
    ({ fast: '快速档', standard: '标准档', premium: '旗舰档' })[props.selectedPreset || 'fast'] ||
    '当前档位',
)
const autoBodyError = computed(() =>
  generateChapters.value && numChapters.value > 20
    ? '自动生成正文单次最多 20 章，请减少本次数量。'
    : '',
)

// 预计总章数默认不代填（0 = 不下发，后端保持中性不注入进度阶段提示）。
// 严禁用「现有大纲数 + N」代填：那等于替用户断言全书快写完了——250 章的长篇
// 会被推进 ≥90% 收束期，后端据此明确引导 LLM 安排结局。仅当蓝图有分卷规划时
// 用分卷覆盖的总章数代填（这是蓝图真实声明的全书规模，不是猜测）。
watch(
  () => props.show,
  (show) => {
    if (show) generateChapters.value = false
    if (show && estimatedTotal.value === 0) {
      const volumes = novelStore.currentProject?.blueprint?.volumes || []
      const volumeEnd = Math.max(0, ...volumes.map((v: any) => v?.end_chapter || 0))
      if (volumeEnd > 0) {
        estimatedTotal.value = volumeEnd
      }
    }
  },
)

const totalPresets = [
  { label: '100万字 (≈334章)', value: 334 },
  { label: '200万字 (≈667章)', value: 667 },
  { label: '300万字 (≈1000章)', value: 1000 },
]

const setNumChapters = (count: number) => {
  numChapters.value = count
}

const handleGenerate = () => {
  if (numChapters.value > 0 && !autoBodyError.value) {
    emit(
      'generate',
      numChapters.value,
      estimatedTotal.value > 0 ? estimatedTotal.value : undefined,
      userPrompt.value,
      generateChapters.value,
    )
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

.m3-preset-btn {
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
}

.auto-body-option {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 12px;
  cursor: pointer;
  background: var(--md-surface-container-low);
  transition: 0.18s ease;
}
.auto-body-option.selected {
  border-color: color-mix(in srgb, var(--md-primary) 55%, transparent);
  background: color-mix(in srgb, var(--md-primary) 8%, var(--md-surface-container-low));
}
.auto-body-option > input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.option-check {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border: 1px solid var(--md-outline);
  border-radius: 6px;
  color: #10110e;
  background: transparent;
}
.option-check svg {
  width: 15px;
  opacity: 0;
}
.auto-body-option.selected .option-check {
  border-color: var(--md-primary);
  background: var(--md-primary);
}
.auto-body-option.selected .option-check svg {
  opacity: 1;
}
.auto-body-option strong,
.auto-body-option small {
  display: block;
}
.auto-body-option strong {
  color: var(--md-on-surface);
  font-size: 0.9rem;
}
.auto-body-option small {
  margin-top: 5px;
  color: var(--md-on-surface-variant);
  font-size: 0.75rem;
  line-height: 1.55;
}
.auto-body-error {
  margin: 8px 2px 0;
  color: #ff8b8b;
  font-size: 0.75rem;
}
</style>
