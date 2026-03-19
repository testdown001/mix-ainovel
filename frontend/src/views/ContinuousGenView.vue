<template>
  <div class="cg-root">
    <div class="cg-header">
      <div>
        <h1 class="cg-title">CONTINUOUS GENERATION</h1>
        <p class="cg-subtitle">AI 连续创作中心 · Novel #{{ id?.slice(0, 8) }}</p>
      </div>
      <div class="cg-controls-top">
        <button class="cg-ctrl-btn cg-ctrl-btn--pause" @click="isPaused = !isPaused">
          {{ isPaused ? '▶ Resume' : '⏸ Pause' }}
        </button>
        <button class="cg-ctrl-btn">⏭ Skip</button>
        <button class="cg-ctrl-btn">✋ Intervene</button>
      </div>
    </div>

    <div class="cg-body">
      <div class="cg-main">
        <div class="cg-output">
          <div class="cg-output-header">
            <span class="cg-output-label">STREAMING OUTPUT</span>
            <span class="cg-output-status">
              <span class="neon-pulse" :class="isPaused ? 'neon-pulse-primary' : ''"></span>
              {{ isPaused ? 'PAUSED' : 'GENERATING' }}
            </span>
          </div>
          <div class="cg-prose font-manuscript">
            <p>雨水沿着霓虹灯管滑落，在混凝土地面上溅起微小的光斑。凯站在天桥上，望着下方永不停歇的车流。每一辆车的尾灯都像是一个即将被遗忘的记忆碎片。</p>
            <p>他伸出右手——那只已经被机械义肢替换的手——感受着人造指尖传来的微弱触觉信号。三年了，他依然无法完全习惯这种模拟的温度。</p>
            <p>"你在想什么？"身后传来萨拉的声音。她的全息投影在雨中微微闪烁，像一个即将消散的梦境。</p>
            <p class="cg-generating">凯没有回头。"我在想，如果记忆真的可以被编辑，那'我'还是'我'吗？"<span class="cg-cursor"></span></p>
          </div>
        </div>

        <div class="cg-context">
          <div class="cg-section-label">CONTEXT INJECTOR</div>
          <div class="cg-context-grid">
            <div class="cg-context-group">
              <span class="cg-context-title">Characters</span>
              <label v-for="c in characters" :key="c" class="cg-check">
                <input type="checkbox" :checked="c.active" />
                <span>{{ c.name }}</span>
              </label>
            </div>
            <div class="cg-context-group">
              <span class="cg-context-title">Settings</span>
              <div class="cg-tags">
                <span v-for="s in settings" :key="s" class="cg-tag">{{ s }}</span>
              </div>
            </div>
            <div class="cg-context-group">
              <span class="cg-context-title">Beat Notes</span>
              <textarea class="cg-beat-input" placeholder="添加关键情节节拍...">凯必须在本章做出抉择</textarea>
            </div>
          </div>
        </div>
      </div>

      <div class="cg-panel">
        <div class="cg-panel-section">
          <div class="cg-section-label">GENERATION STATS</div>
          <div class="cg-stat-row"><span>Generated Words</span><span class="cg-stat-val">1,247</span></div>
          <div class="cg-stat-row"><span>Speed</span><span class="cg-stat-val">42 tok/s</span></div>
          <div class="cg-stat-row"><span>Context Usage</span><span class="cg-stat-val">67%</span></div>
          <div class="cg-stat-row"><span>Quality Score</span><span class="cg-stat-val cg-stat-val--green">89</span></div>
        </div>

        <div class="cg-panel-section">
          <div class="cg-section-label">UPCOMING QUEUE</div>
          <div class="cg-queue">
            <div v-for="q in queue" :key="q.id" class="cg-queue-item">
              <span class="cg-queue-dot" :class="'cg-queue-dot--' + q.status"></span>
              <div>
                <div class="cg-queue-name">{{ q.name }}</div>
                <div class="cg-queue-meta">{{ q.meta }}</div>
              </div>
            </div>
          </div>
          <button class="cg-batch-btn">Batch Generate (5 chapters)</button>
        </div>

        <div class="cg-panel-section">
          <div class="cg-section-label">ADJUSTMENT</div>
          <div class="cg-adj-row">
            <span>Temperature</span>
            <input type="range" min="0" max="100" value="70" class="neon-slider" />
          </div>
          <div class="cg-adj-row">
            <span>Creativity</span>
            <input type="range" min="0" max="100" value="55" class="neon-slider" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ id: string }>()

const isPaused = ref(false)

const characters = [
  { name: '凯 (Kai)', active: true },
  { name: '萨拉 (Sara)', active: true },
  { name: '博士', active: false },
  { name: '机械心', active: false },
]

const settings = ['霓虹城', '地下实验室', '天桥', '记忆代码']

const queue = [
  { id: 1, name: '第43章：记忆的边界', meta: '预计 3,200 字', status: 'active' },
  { id: 2, name: '第44章：觉醒时刻', meta: '预计 2,800 字', status: 'pending' },
  { id: 3, name: '第45章：最终抉择', meta: '预计 3,500 字', status: 'pending' },
]
</script>

<style scoped>
.cg-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.cg-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
.cg-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.cg-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.cg-controls-top { display: flex; gap: 8px; }
.cg-ctrl-btn { padding: 8px 16px; border: 1px solid rgba(77,70,50,0.3); border-radius: 4px; background: var(--ar-bg-surface); color: var(--ar-text-primary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.cg-ctrl-btn:hover { border-color: var(--ar-primary); color: var(--ar-primary); }
.cg-ctrl-btn--pause { background: var(--ar-primary); color: var(--ar-on-primary); border-color: var(--ar-primary); }
.cg-body { display: grid; grid-template-columns: 1fr 300px; gap: 24px; }
.cg-main { display: flex; flex-direction: column; gap: 20px; }
.cg-output { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; }
.cg-output-header { display: flex; justify-content: space-between; margin-bottom: 16px; }
.cg-output-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; }
.cg-output-status { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: var(--ar-secondary); letter-spacing: 0.04em; }
.cg-prose { font-family: var(--ar-font-manuscript); font-size: 16px; line-height: 1.9; color: var(--ar-text-primary); }
.cg-prose p { margin-bottom: 16px; }
.cg-generating { color: var(--ar-secondary); font-style: italic; }
.cg-cursor { display: inline-block; width: 2px; height: 18px; background: var(--ar-secondary); animation: blink 1s step-end infinite; vertical-align: text-bottom; margin-left: 2px; }
@keyframes blink { 50% { opacity: 0; } }
.cg-context { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.cg-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 12px; }
.cg-context-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.cg-context-title { font-size: 12px; font-weight: 600; color: var(--ar-text-secondary); display: block; margin-bottom: 8px; }
.cg-check { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--ar-text-secondary); cursor: pointer; margin-bottom: 4px; }
.cg-check input { accent-color: var(--ar-secondary); }
.cg-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.cg-tag { padding: 4px 10px; border-radius: 2px; background: var(--ar-bg-highlight); font-size: 11px; color: var(--ar-text-primary); font-weight: 500; }
.cg-beat-input { width: 100%; min-height: 60px; background: var(--ar-bg-elevated); border: none; border-radius: 4px; padding: 8px 12px; font-size: 13px; color: var(--ar-text-primary); resize: vertical; outline: none; font-family: var(--ar-font-ui); }
.cg-panel { display: flex; flex-direction: column; gap: 16px; }
.cg-panel-section { background: var(--ar-bg-surface); border-radius: 4px; padding: 16px; }
.cg-stat-row { display: flex; justify-content: space-between; font-size: 13px; color: var(--ar-text-muted); padding: 6px 0; }
.cg-stat-val { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-text-primary); }
.cg-stat-val--green { color: var(--ar-secondary); }
.cg-queue { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.cg-queue-item { display: flex; align-items: center; gap: 10px; padding: 10px; background: var(--ar-bg-elevated); border-radius: 4px; }
.cg-queue-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cg-queue-dot--active { background: var(--ar-secondary); box-shadow: 0 0 8px rgba(74,222,128,0.5); }
.cg-queue-dot--pending { background: var(--ar-text-muted); }
.cg-queue-name { font-size: 13px; font-weight: 500; color: var(--ar-text-primary); }
.cg-queue-meta { font-size: 11px; color: var(--ar-text-muted); }
.cg-batch-btn { width: 100%; padding: 10px; border: 1px solid rgba(77,70,50,0.2); border-radius: 4px; background: transparent; color: var(--ar-primary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.cg-batch-btn:hover { background: var(--ar-primary-muted); }
.cg-adj-row { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--ar-text-secondary); margin-bottom: 8px; }
.cg-adj-row span { min-width: 80px; }
.neon-slider { flex: 1; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--ar-bg-highlight); outline: none; }
.neon-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--ar-primary); cursor: pointer; box-shadow: 0 0 8px rgba(250,204,21,0.4); }
</style>
