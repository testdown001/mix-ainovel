<template>
  <div class="tl-root">
    <div class="tl-header">
      <div>
        <h1 class="tl-title">TIMELINE CORE</h1>
        <p class="tl-subtitle">叙事时间线模拟器 · Novel #{{ id?.slice(0, 8) }}</p>
      </div>
      <button class="tl-sim-btn" @click="simulating = !simulating">
        <span class="neon-pulse" :class="simulating ? '' : 'neon-pulse-primary'" style="width:6px;height:6px;"></span>
        {{ simulating ? 'Stop Simulation' : 'Start Simulation' }}
      </button>
    </div>

    <div class="tl-body">
      <div class="tl-main">
        <div class="tl-tree">
          <div class="tl-section-label">NARRATIVE DIVERGENCE TREE</div>
          <div class="tl-tree-visual">
            <div class="tl-path tl-path--main">
              <div class="tl-node tl-node--root">Origin</div>
              <div class="tl-line"></div>
              <div class="tl-node">Event A</div>
              <div class="tl-line"></div>
              <div class="tl-fork">
                <div class="tl-branch">
                  <div class="tl-node tl-node--active">Path α: 记忆保留</div>
                  <div class="tl-line tl-line--short"></div>
                  <div class="tl-node">Outcome: 和平</div>
                </div>
                <div class="tl-branch">
                  <div class="tl-node">Path β: 记忆删除</div>
                  <div class="tl-line tl-line--short"></div>
                  <div class="tl-node tl-node--danger">Outcome: 冲突</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="tl-chronicle">
          <div class="tl-section-label">CHRONICLE LOG</div>
          <div class="tl-log-list">
            <div v-for="log in logs" :key="log.id" class="tl-log-item">
              <span class="tl-log-time">T+{{ log.time }}</span>
              <span class="tl-log-text">{{ log.text }}</span>
              <span v-if="log.fix" class="tl-log-fix">Fix: {{ log.fix }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="tl-panel">
        <div class="tl-panel-section">
          <div class="tl-section-label">SIMULATION CONTROLS</div>
          <div class="tl-ctrl-row"><span>Chaos Factor</span><input type="range" min="0" max="100" v-model="chaos" class="neon-slider" /><span class="tl-ctrl-val">{{ chaos }}%</span></div>
          <div class="tl-ctrl-row"><span>Timeline Length</span><input type="range" min="1" max="50" v-model="length" class="neon-slider" /><span class="tl-ctrl-val">{{ length }} ch</span></div>
          <div class="tl-ctrl-item">
            <span>Character Focus</span>
            <select class="tl-select" v-model="focusChar">
              <option v-for="c in chars" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
        </div>

        <div class="tl-panel-section">
          <div class="tl-section-label">PATH METRICS</div>
          <div v-for="m in metrics" :key="m.label" class="tl-metric">
            <div class="tl-metric-header"><span>{{ m.label }}</span><span class="tl-metric-val">{{ m.value }}</span></div>
            <div class="tl-metric-bar"><div class="tl-metric-fill" :style="{ width: m.pct + '%', background: m.color }"></div></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ id: string }>()

const simulating = ref(false)
const chaos = ref(35)
const length = ref(12)
const focusChar = ref('凯')
const chars = ['凯', '萨拉', '博士', '全部角色']

const logs = [
  { id: 1, time: '0:00', text: '凯在天桥上做出抉择', fix: null },
  { id: 2, time: '2:34', text: '萨拉的全息投影消失', fix: '增加情感过渡段落' },
  { id: 3, time: '5:12', text: '记忆代码激活', fix: null },
  { id: 4, time: '8:45', text: '时间线分裂: α/β路径产生', fix: '需要伏笔回收 #3' },
]

const metrics = [
  { label: 'Path α Coherence', value: '92%', pct: 92, color: 'var(--ar-secondary)' },
  { label: 'Path β Coherence', value: '67%', pct: 67, color: 'var(--ar-primary)' },
  { label: 'Character Consistency', value: '85%', pct: 85, color: 'var(--ar-secondary)' },
  { label: 'Emotional Impact', value: '78%', pct: 78, color: 'var(--ar-primary)' },
]
</script>

<style scoped>
.tl-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.tl-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
.tl-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.tl-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.tl-sim-btn { display: flex; align-items: center; gap: 8px; padding: 10px 20px; border: 1px solid rgba(77,70,50,0.3); border-radius: 4px; background: var(--ar-bg-surface); color: var(--ar-text-primary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.tl-sim-btn:hover { border-color: var(--ar-primary); }
.tl-body { display: grid; grid-template-columns: 1fr 300px; gap: 24px; }
.tl-main { display: flex; flex-direction: column; gap: 20px; }
.tl-tree { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; min-height: 300px; }
.tl-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.tl-tree-visual { display: flex; justify-content: center; }
.tl-path { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.tl-node { background: var(--ar-bg-elevated); border-radius: 4px; padding: 10px 20px; font-size: 13px; color: var(--ar-text-primary); border: 1px solid rgba(77,70,50,0.15); }
.tl-node--root { border-color: var(--ar-secondary); color: var(--ar-secondary); }
.tl-node--active { border-color: var(--ar-primary); color: var(--ar-primary); box-shadow: 0 0 16px rgba(250,204,21,0.1); }
.tl-node--danger { border-color: var(--ar-error); color: var(--ar-error); }
.tl-line { width: 2px; height: 24px; background: rgba(77,70,50,0.2); }
.tl-line--short { height: 16px; }
.tl-fork { display: flex; gap: 40px; }
.tl-branch { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.tl-chronicle { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.tl-log-list { display: flex; flex-direction: column; gap: 8px; }
.tl-log-item { display: flex; align-items: flex-start; gap: 12px; padding: 10px; background: var(--ar-bg-elevated); border-radius: 4px; font-size: 13px; }
.tl-log-time { font-family: var(--ar-font-mono); font-size: 11px; color: var(--ar-text-muted); min-width: 40px; }
.tl-log-text { flex: 1; color: var(--ar-text-primary); }
.tl-log-fix { font-size: 11px; color: var(--ar-primary); font-style: italic; }
.tl-panel { display: flex; flex-direction: column; gap: 16px; }
.tl-panel-section { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.tl-ctrl-row { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--ar-text-secondary); margin-bottom: 12px; }
.tl-ctrl-row span:first-child { min-width: 100px; }
.tl-ctrl-val { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-primary); min-width: 40px; text-align: right; }
.tl-ctrl-item { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--ar-text-secondary); }
.tl-ctrl-item span { min-width: 100px; }
.tl-select { flex: 1; padding: 8px 12px; background: var(--ar-bg-elevated); border: 1px solid rgba(77,70,50,0.15); border-radius: 4px; color: var(--ar-text-primary); font-size: 13px; outline: none; }
.tl-metric { margin-bottom: 14px; }
.tl-metric-header { display: flex; justify-content: space-between; font-size: 12px; color: var(--ar-text-secondary); margin-bottom: 6px; }
.tl-metric-val { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-text-primary); }
.tl-metric-bar { height: 4px; background: rgba(77,70,50,0.1); border-radius: 2px; }
.tl-metric-fill { height: 100%; border-radius: 2px; transition: width 0.4s; }
.neon-slider { flex: 1; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--ar-bg-highlight); outline: none; }
.neon-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--ar-primary); cursor: pointer; box-shadow: 0 0 8px rgba(250,204,21,0.4); }
</style>
