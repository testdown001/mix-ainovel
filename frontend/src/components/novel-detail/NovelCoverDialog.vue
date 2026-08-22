<!-- AIMETA P=小说封面生成弹窗|R=封面参数_预览_生成|NR=不负责图片存储|E=component:NovelCoverDialog|X=ui|A=封面生成表单|D=vue|S=dom|RD=./README.ai -->
<template>
  <Teleport to="body">
    <transition name="cover-dialog">
      <div v-if="show" class="cover-dialog-mask" @click.self="$emit('close')">
        <section class="cover-dialog" role="dialog" aria-modal="true" aria-labelledby="cover-dialog-title">
          <div class="cover-dialog__head">
            <div>
              <p class="cover-dialog__eyebrow">GPT-IMAGE-2 · AI 封面工作室</p>
              <h2 id="cover-dialog-title">为《{{ title }}》生成封面</h2>
              <p>系统会结合题材与故事梗概生成 2:3 竖版主视觉。</p>
            </div>
            <button type="button" class="cover-dialog__close" aria-label="关闭" @click="$emit('close')">×</button>
          </div>

          <div class="cover-dialog__body">
            <div class="cover-dialog__preview">
              <img v-if="currentCoverUrl" :src="currentCoverUrl" :alt="`${title} 当前封面`">
              <div v-else class="cover-dialog__empty">
                <span>✦</span>
                <strong>等待生成</strong>
                <small>1024 × 1536</small>
              </div>
              <div v-if="generating" class="cover-dialog__generating">
                <i></i>
                <strong>正在构思封面</strong>
                <span>通常需要 30 秒至数分钟，请不要关闭页面</span>
              </div>
            </div>

            <div class="cover-dialog__form">
              <label>
                <span>艺术方向</span>
                <textarea
                  v-model="artDirection"
                  rows="6"
                  maxlength="800"
                  placeholder="例如：东方废土工业风，黑金与暗红配色，巨型矿城剪影，人物背影居中……"
                ></textarea>
                <small>{{ artDirection.length }}/800 · 可描述构图、色彩、人物与氛围</small>
              </label>

              <fieldset>
                <legend>生成质量</legend>
                <button
                  v-for="option in qualityOptions"
                  :key="option.value"
                  type="button"
                  :class="{ active: quality === option.value }"
                  @click="quality = option.value"
                >
                  <strong>{{ option.label }}</strong>
                  <small>{{ option.hint }}</small>
                </button>
              </fieldset>

              <label class="cover-dialog__switch">
                <input v-model="includeTitle" type="checkbox">
                <span class="cover-dialog__switch-track"><i></i></span>
                <span>
                  <strong>在画面中排版书名</strong>
                  <small>中文文字偶尔会有偏差，可关闭后自行排版</small>
                </span>
              </label>

              <p v-if="error" class="cover-dialog__error">{{ error }}</p>
            </div>
          </div>

          <div class="cover-dialog__foot">
            <span v-if="optionsLoading">正在确认生成权限与价格…</span>
            <span v-else-if="canGenerate">每次生成消耗 {{ creditPrice }} 积分，失败自动退回</span>
            <span v-else>当前套餐不可用，需升级至{{ requiredTierLabel }}</span>
            <div>
              <button type="button" class="cover-btn cover-btn--ghost" :disabled="generating" @click="$emit('close')">取消</button>
              <button
                type="button"
                class="cover-btn cover-btn--primary"
                :disabled="generating || optionsLoading || !canGenerate || !artDirection.trim()"
                @click="submit"
              >
                {{ generating ? '生成中…' : !canGenerate ? '升级套餐后使用' : currentCoverUrl ? '重新生成' : '生成封面' }}
              </button>
            </div>
          </div>
        </section>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { GenerateCoverPayload } from '@/api/novel'

const props = defineProps<{
  show: boolean
  title: string
  currentCoverUrl: string
  generating: boolean
  error: string
  optionsLoading: boolean
  canGenerate: boolean
  creditPrice: number
  requiredTier: 'free' | 'creator' | 'flagship'
}>()

const emit = defineEmits<{
  close: []
  generate: [payload: GenerateCoverPayload]
}>()

const artDirection = ref('电影感东方幻想，克制高级，黑金主色，强光影与清晰主视觉，适合网络小说竖版封面')
const quality = ref<'low' | 'medium' | 'high'>('medium')
const includeTitle = ref(true)
const tierLabels = { free: '免费版', creator: '创作者版', flagship: '旗舰版' } as const
const requiredTierLabel = computed(() => tierLabels[props.requiredTier])

const qualityOptions = [
  { value: 'low' as const, label: '快速', hint: '适合试稿' },
  { value: 'medium' as const, label: '标准', hint: '推荐选择' },
  { value: 'high' as const, label: '精细', hint: '细节更多' }
]

watch(() => props.show, (visible) => {
  if (visible) includeTitle.value = true
})

const submit = () => {
  emit('generate', {
    art_direction: artDirection.value.trim(),
    quality: quality.value,
    include_title: includeTitle.value
  })
}
</script>

<style scoped>
.cover-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.78);
  backdrop-filter: blur(14px);
}
.cover-dialog {
  width: min(920px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  color: #f7f7f2;
  background: #111;
  border: 1px solid #303026;
  border-radius: 24px;
  box-shadow: 0 28px 100px rgba(0, 0, 0, 0.62);
}
.cover-dialog__head,
.cover-dialog__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
}
.cover-dialog__head { border-bottom: 1px solid #282822; }
.cover-dialog__head h2 { margin: 4px 0 5px; font-size: 22px; font-weight: 750; }
.cover-dialog__head p:not(.cover-dialog__eyebrow) { margin: 0; color: #888880; font-size: 13px; }
.cover-dialog__eyebrow { margin: 0; color: #ffe500; font-size: 10px; font-weight: 800; letter-spacing: 0.16em; }
.cover-dialog__close { width: 36px; height: 36px; color: #898982; font-size: 25px; background: #1b1b18; border: 1px solid #30302a; border-radius: 50%; }
.cover-dialog__body { display: grid; grid-template-columns: 280px 1fr; gap: 28px; padding: 26px; }
.cover-dialog__preview { position: relative; aspect-ratio: 2 / 3; overflow: hidden; background: radial-gradient(circle at 50% 22%, #47400a 0, #1b1a0d 35%, #10100e 75%); border: 1px solid #38372b; border-radius: 18px; }
.cover-dialog__preview img { width: 100%; height: 100%; object-fit: cover; }
.cover-dialog__empty { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #77776f; }
.cover-dialog__empty span { color: #ffe500; font-size: 38px; }
.cover-dialog__empty strong { color: #d6d6ce; }
.cover-dialog__empty small { font-size: 11px; letter-spacing: 0.12em; }
.cover-dialog__generating { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 24px; text-align: center; background: rgba(8, 8, 7, 0.87); }
.cover-dialog__generating i { width: 38px; height: 38px; border: 2px solid #39382f; border-top-color: #ffe500; border-radius: 50%; animation: cover-spin 0.8s linear infinite; }
.cover-dialog__generating span { color: #8e8e86; font-size: 12px; line-height: 1.6; }
.cover-dialog__form { display: flex; flex-direction: column; gap: 22px; }
.cover-dialog__form label > span:first-child,
.cover-dialog__form legend { display: block; margin-bottom: 9px; color: #e9e9e3; font-size: 13px; font-weight: 700; }
.cover-dialog__form textarea { width: 100%; padding: 14px 15px; resize: vertical; color: #eee; line-height: 1.65; background: #191917; border: 1px solid #33332d; border-radius: 12px; outline: none; }
.cover-dialog__form textarea:focus { border-color: #ffe500; box-shadow: 0 0 0 3px rgba(255, 229, 0, 0.08); }
.cover-dialog__form label > small { display: block; margin-top: 7px; color: #777770; font-size: 11px; }
.cover-dialog__form fieldset { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 0; border: 0; }
.cover-dialog__form legend { grid-column: 1 / -1; }
.cover-dialog__form fieldset button { display: flex; flex-direction: column; gap: 3px; padding: 11px 12px; text-align: left; color: #a4a49d; background: #181816; border: 1px solid #30302a; border-radius: 11px; }
.cover-dialog__form fieldset button.active { color: #ffe500; background: rgba(255, 229, 0, 0.08); border-color: #9e9000; }
.cover-dialog__form fieldset small { color: #707069; font-size: 10px; }
.cover-dialog__switch { display: flex; align-items: center; gap: 11px; cursor: pointer; }
.cover-dialog__switch input { position: absolute; opacity: 0; }
.cover-dialog__switch-track { position: relative; flex: 0 0 auto; width: 42px; height: 24px; margin: 0 !important; background: #393933; border-radius: 99px; transition: 0.2s; }
.cover-dialog__switch-track i { position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; background: #aaa; border-radius: 50%; transition: 0.2s; }
.cover-dialog__switch input:checked + .cover-dialog__switch-track { background: #ffe500; }
.cover-dialog__switch input:checked + .cover-dialog__switch-track i { left: 21px; background: #111; }
.cover-dialog__switch > span:last-child { display: flex; flex-direction: column; gap: 3px; }
.cover-dialog__switch strong { font-size: 13px; }
.cover-dialog__switch small { color: #777770; font-size: 11px; }
.cover-dialog__error { margin: 0; padding: 10px 12px; color: #ff8a93; font-size: 12px; line-height: 1.5; background: rgba(255, 71, 87, 0.09); border: 1px solid rgba(255, 71, 87, 0.25); border-radius: 10px; }
.cover-dialog__foot { border-top: 1px solid #282822; }
.cover-dialog__foot > span { color: #6f6f69; font-size: 11px; }
.cover-dialog__foot > div { display: flex; gap: 10px; }
.cover-btn { min-width: 96px; padding: 10px 18px; font-size: 13px; font-weight: 750; border-radius: 10px; }
.cover-btn:disabled { cursor: not-allowed; opacity: 0.45; }
.cover-btn--ghost { color: #aaa; background: transparent; border: 1px solid #35352f; }
.cover-btn--primary { color: #0a0a09; background: #ffe500; border: 1px solid #ffe500; }
.cover-dialog-enter-active, .cover-dialog-leave-active { transition: opacity 0.2s ease; }
.cover-dialog-enter-from, .cover-dialog-leave-to { opacity: 0; }
@keyframes cover-spin { to { transform: rotate(360deg); } }
@media (max-width: 720px) {
  .cover-dialog-mask { padding: 10px; }
  .cover-dialog { max-height: calc(100vh - 20px); border-radius: 18px; }
  .cover-dialog__body { grid-template-columns: 120px 1fr; gap: 16px; padding: 18px; }
  .cover-dialog__head, .cover-dialog__foot { padding: 18px; }
}
@media (max-width: 520px) {
  .cover-dialog__body { grid-template-columns: 1fr; }
  .cover-dialog__preview { width: 150px; margin: 0 auto; }
  .cover-dialog__foot > span { display: none; }
  .cover-dialog__foot { justify-content: flex-end; }
}
</style>
