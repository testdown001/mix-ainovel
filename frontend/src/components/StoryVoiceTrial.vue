<script setup lang="ts">
import { ref, watch } from 'vue'
import { NovelAPI, type ConceptDossier, type VoiceTrial } from '@/api/novel'

const props = defineProps<{ projectId: string; dossier: ConceptDossier }>()
const trial = ref<VoiceTrial | null>(null)
const scene = ref('')
const busy = ref(false)
const error = ref('')
const message = ref('')
let loadSequence = 0

watch(() => [props.projectId, props.dossier] as const, async () => {
  const sequence = ++loadSequence
  trial.value = null
  busy.value = false
  error.value = ''
  message.value = ''
  try {
    const result = await NovelAPI.getVoiceTrial(props.projectId)
    if (sequence === loadSequence) trial.value = result.trial
  } catch {
    if (sequence === loadSequence) error.value = '口吻试写暂时无法加载，可继续完善立项书。'
  }
}, { immediate: true })

const generate = async () => {
  busy.value = true
  error.value = ''
  message.value = ''
  const projectId = props.projectId
  const sequence = ++loadSequence
  try {
    const result = await NovelAPI.generateVoiceTrial(projectId, scene.value.trim())
    if (sequence === loadSequence) trial.value = result.trial
  } catch (e) {
    if (sequence === loadSequence) error.value = e instanceof Error ? e.message : '试写未完成，请稍后重试。'
  } finally {
    if (sequence === loadSequence) busy.value = false
  }
}

const select = async (candidateId: string) => {
  if (!trial.value || trial.value.stale) return
  busy.value = true
  error.value = ''
  message.value = ''
  const sequence = ++loadSequence
  try {
    const result = await NovelAPI.selectVoiceTrial(props.projectId, trial.value.id, candidateId)
    if (sequence !== loadSequence) return
    trial.value = result.trial
    message.value = '已保存为本书口吻，后续章节会参考；也可以在创作记忆中修改或停用。'
  } catch (e) {
    if (sequence === loadSequence) error.value = e instanceof Error ? e.message : '保存口吻失败，请重试。'
  } finally {
    if (sequence === loadSequence) busy.value = false
  }
}
</script>

<template>
  <section class="voice-trial" :aria-busy="busy">
    <div class="voice-heading"><h3>先读一小段，选定口吻</h3><span>可选</span></div>
    <p class="voice-hint">用同一场景比较对白、停顿和叙述方式。喜欢哪一版，再让这本书沿用它。</p>
    <label for="voice-scene">想试写的情节</label>
    <textarea id="voice-scene" v-model="scene" maxlength="600" rows="2" :disabled="busy"
      placeholder="例如：他拿出攒了很久的钱替师弟买药，却坚持说只是借款。留空则从当前设定选一个小场景。" />
    <button type="button" class="voice-generate" :disabled="busy" @click="generate">
      {{ busy ? '正在处理，请稍候…' : trial ? '换一组口吻' : '试写几种口吻' }}
    </button>
    <p v-if="trial" class="voice-hint">换一组只会生成新候选，已采用的口吻会保留到你再次选择。</p>
    <p v-if="trial?.stale" class="voice-notice">立项书已修改，请重新试写后再选择口吻。</p>
    <p v-if="trial" class="voice-scene">共用场景：{{ trial.scene }}</p>
    <div v-if="trial" class="voice-candidates">
      <article v-for="candidate in trial.candidates" :key="candidate.id"
        :class="['voice-card', { selected: trial.selected_id === candidate.id }]">
        <h4>{{ candidate.label }}</h4>
        <p class="voice-notes">{{ candidate.style_notes }}</p>
        <p class="voice-prose">{{ candidate.text }}</p>
        <button type="button" :disabled="busy || trial.stale || trial.selected_id === candidate.id"
          :aria-pressed="trial.selected_id === candidate.id" @click="select(candidate.id)">
          {{ trial.selected_id === candidate.id ? '已采用此口吻' : '这段有味道，采用此口吻' }}
        </button>
      </article>
    </div>
    <p v-if="message" class="voice-success" role="status">{{ message }}</p>
    <p v-if="error" class="voice-error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.voice-trial { padding: 20px; border: 1px solid #3d3d46; border-radius: 14px; background: #202027; color: #e7e5e4; }
.voice-heading { display: flex; align-items: center; gap: 12px; }
.voice-heading h3 { margin: 0; font-size: 16px; }
.voice-heading span { color: #bbb3a7; font-size: 12px; }
.voice-hint, .voice-notes { color: #bbb7b2; font-size: 13px; line-height: 1.7; margin: 10px 0; }
label { display: block; margin: 14px 0 7px; font-size: 13px; }
textarea { box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid #52525b; border-radius: 8px; background: #18181d; color: #eee; padding: 10px; font: inherit; font-size: 13px; }
button { padding: 9px 14px; border: 1px solid #62606a; border-radius: 8px; color: #eee; background: #33313b; cursor: pointer; font-size: 13px; }
button:disabled { opacity: .55; cursor: default; }
button:focus-visible, textarea:focus-visible { outline: 2px solid #d0b885; outline-offset: 3px; }
.voice-generate { margin-top: 10px; }
.voice-candidates { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 250px), 1fr)); gap: 12px; margin-top: 14px; }
.voice-card { border: 1px solid #46454d; border-radius: 10px; padding: 16px; display: flex; flex-direction: column; }
.voice-card.selected { border-color: #c9ac71; background: #292720; }
.voice-card h4 { font-size: 15px; margin: 0; }
.voice-prose { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.95; font-size: 14px; flex: 1; margin: 12px 0 20px; }
.voice-scene, .voice-notice, .voice-success, .voice-error { font-size: 13px; line-height: 1.7; margin-top: 12px; }
.voice-scene, .voice-notice { color: #dcc89e; }
.voice-success { color: #a8d5b0; }
.voice-error { color: #f0a6a6; }
</style>
