<template>
  <div class="plotlab-root">
    <div class="plotlab-header">
      <div>
        <h1 class="plotlab-title">PLOT LAB</h1>
        <p class="plotlab-subtitle">AI 情节推演实验室 · Novel #{{ id?.slice(0, 8) }}</p>
      </div>
      <div class="plotlab-status">
        <span class="neon-pulse"></span>
        <span class="plotlab-status-text">AI Engine Active</span>
      </div>
    </div>

    <div class="plotlab-body">
      <div class="plotlab-main">
        <div class="plotlab-canvas">
          <div class="plotlab-section-label">PLOT FLOWCHART</div>
          <div class="plotlab-nodes">
            <div class="plot-node plot-node--start">开篇：异世界觉醒</div>
            <div class="plot-connector"></div>
            <div class="plot-node">第一幕：身份危机</div>
            <div class="plot-connector"></div>
            <div class="plot-branch">
              <div class="plot-node plot-node--active">路线A：接受命运</div>
              <div class="plot-node">路线B：反抗系统</div>
            </div>
            <div class="plot-connector"></div>
            <div class="plot-node">高潮：最终决战</div>
            <div class="plot-connector"></div>
            <div class="plot-node plot-node--end">结局：新世界秩序</div>
          </div>
        </div>

        <div class="plotlab-deduction">
          <div class="plotlab-section-label">CHAPTER DEDUCTION TREE</div>
          <div class="deduction-list">
            <div v-for="ch in chapters" :key="ch.id" class="deduction-item" @click="ch.open = !ch.open">
              <span class="deduction-arrow" :class="{ 'deduction-arrow--open': ch.open }">▸</span>
              <span class="deduction-ch">Ch.{{ ch.id }}</span>
              <span class="deduction-name">{{ ch.name }}</span>
              <span class="deduction-score">{{ ch.score }}%</span>
            </div>
          </div>
        </div>
      </div>

      <div class="plotlab-panel">
        <div class="panel-section">
          <div class="panel-label">CONFLICT INTENSITY</div>
          <input type="range" min="0" max="100" v-model="conflictIntensity" class="neon-slider" />
          <div class="panel-value">{{ conflictIntensity }}%</div>
        </div>

        <div class="panel-section">
          <div class="panel-label">ENDING PATH</div>
          <div class="panel-options">
            <button v-for="p in paths" :key="p" class="panel-option" :class="{ 'panel-option--active': selectedPath === p }" @click="selectedPath = p">{{ p }}</button>
          </div>
        </div>

        <div class="panel-section">
          <div class="panel-label">AI LOGIC AUDIT</div>
          <div class="audit-list">
            <div class="audit-item audit-item--warn">
              <span class="neon-pulse neon-pulse-primary" style="width:6px;height:6px;"></span>
              角色"凯"在第12章出现动机不一致
            </div>
            <div class="audit-item audit-item--ok">
              <span class="neon-pulse" style="width:6px;height:6px;"></span>
              世界观设定一致性: 92%
            </div>
            <div class="audit-item audit-item--warn">
              <span class="neon-pulse neon-pulse-primary" style="width:6px;height:6px;"></span>
              伏笔 #7 尚未回收
            </div>
          </div>
        </div>

        <div class="panel-section">
          <div class="panel-label">GENERATION QUEUE</div>
          <div class="queue-list">
            <div v-for="q in queue" :key="q.id" class="queue-item">
              <span class="queue-status" :class="'queue-status--' + q.status"></span>
              {{ q.label }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'

defineProps<{ id: string }>()

const conflictIntensity = ref(65)
const selectedPath = ref('Happy End')
const paths = ['Happy End', 'Tragic', 'Open-Ended', 'Bittersweet']

const chapters = reactive([
  { id: 1, name: '异世界觉醒', score: 95, open: false },
  { id: 2, name: '身份危机', score: 88, open: false },
  { id: 3, name: '第一次冲突', score: 72, open: false },
  { id: 4, name: '盟友出现', score: 90, open: false },
  { id: 5, name: '真相揭示', score: 67, open: false },
])

const queue = [
  { id: 1, label: '第6章大纲生成', status: 'active' },
  { id: 2, label: '角色弧线推演', status: 'pending' },
  { id: 3, label: '伏笔回收检查', status: 'pending' },
]
</script>

<style scoped>
.plotlab-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.plotlab-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
.plotlab-title { font-family: var(--ar-font-display); font-size: 32px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.plotlab-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.plotlab-status { display: flex; align-items: center; gap: 8px; }
.plotlab-status-text { font-size: 12px; color: var(--ar-secondary); font-weight: 600; letter-spacing: 0.04em; }
.plotlab-body { display: grid; grid-template-columns: 1fr 320px; gap: 24px; }
.plotlab-main { display: flex; flex-direction: column; gap: 20px; }
.plotlab-canvas { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; min-height: 360px; }
.plotlab-section-label { font-family: var(--ar-font-ui); font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.plotlab-nodes { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.plot-node { background: var(--ar-bg-elevated); border-radius: 4px; padding: 12px 24px; font-size: 14px; font-weight: 500; color: var(--ar-text-primary); text-align: center; border: 1px solid rgba(77,70,50,0.15); width: fit-content; }
.plot-node--start { border-color: var(--ar-secondary); color: var(--ar-secondary); }
.plot-node--active { border-color: var(--ar-primary); color: var(--ar-primary); box-shadow: 0 0 20px rgba(250,204,21,0.1); }
.plot-node--end { border-color: var(--ar-primary); background: var(--ar-primary-muted); }
.plot-connector { width: 2px; height: 20px; background: linear-gradient(to bottom, rgba(77,70,50,0.3), rgba(77,70,50,0.1)); }
.plot-branch { display: flex; gap: 24px; }
.plotlab-deduction { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.deduction-list { display: flex; flex-direction: column; gap: 4px; }
.deduction-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 4px; font-size: 13px; color: var(--ar-text-secondary); cursor: pointer; transition: background 0.15s; }
.deduction-item:hover { background: rgba(255,255,255,0.03); }
.deduction-arrow { color: var(--ar-text-muted); transition: transform 0.15s; }
.deduction-arrow--open { transform: rotate(90deg); }
.deduction-ch { font-family: var(--ar-font-mono); font-size: 11px; color: var(--ar-text-muted); min-width: 36px; }
.deduction-name { flex: 1; color: var(--ar-text-primary); }
.deduction-score { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-secondary); }
.plotlab-panel { display: flex; flex-direction: column; gap: 16px; }
.panel-section { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.panel-label { font-family: var(--ar-font-ui); font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 12px; }
.panel-value { font-family: var(--ar-font-display); font-size: 20px; font-weight: 700; color: var(--ar-primary); margin-top: 8px; }
.neon-slider { width: 100%; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--ar-bg-highlight); outline: none; }
.neon-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%; background: var(--ar-primary); cursor: pointer; box-shadow: 0 0 10px rgba(250,204,21,0.4); }
.panel-options { display: flex; flex-wrap: wrap; gap: 6px; }
.panel-option { padding: 6px 14px; border-radius: 2px; border: 1px solid rgba(77,70,50,0.2); background: transparent; color: var(--ar-text-secondary); font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.15s; }
.panel-option--active { background: var(--ar-primary); color: var(--ar-on-primary); border-color: var(--ar-primary); }
.audit-list { display: flex; flex-direction: column; gap: 8px; }
.audit-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ar-text-secondary); padding: 8px; border-radius: 4px; background: var(--ar-bg-elevated); }
.queue-list { display: flex; flex-direction: column; gap: 6px; }
.queue-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ar-text-secondary); padding: 8px 12px; background: var(--ar-bg-elevated); border-radius: 4px; }
.queue-status { width: 6px; height: 6px; border-radius: 50%; }
.queue-status--active { background: var(--ar-secondary); box-shadow: 0 0 8px rgba(74,222,128,0.5); }
.queue-status--pending { background: var(--ar-text-muted); }
</style>
