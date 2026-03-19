<template>
  <div class="sh-root">
    <div class="sh-header">
      <h1 class="sh-title">SYSTEM HEALTH</h1>
      <p class="sh-subtitle">系统状态监控面板</p>
    </div>

    <div class="sh-grid stagger-reveal">
      <div class="sh-card sh-card--token">
        <div class="sh-section-label">TOKEN BALANCE</div>
        <div class="sh-token-ring">
          <svg viewBox="0 0 80 80" class="sh-ring-svg">
            <circle cx="40" cy="40" r="32" fill="none" stroke="rgba(250,204,21,0.1)" stroke-width="5" />
            <circle cx="40" cy="40" r="32" fill="none" stroke="#FACC15" stroke-width="5"
              stroke-dasharray="140 201" stroke-dashoffset="0" stroke-linecap="round" transform="rotate(-90 40 40)" />
          </svg>
          <div class="sh-ring-text">
            <span class="sh-ring-val">1.24M</span>
            <span class="sh-ring-label">Tokens</span>
          </div>
        </div>
        <div class="sh-renewal">
          <span class="neon-pulse neon-pulse-primary" style="width:5px;height:5px;"></span>
          续期提醒: 距订阅到期还有 12 天
        </div>
      </div>

      <div class="sh-card">
        <div class="sh-section-label">MODEL LATENCY</div>
        <div class="sh-latency-list">
          <div v-for="m in models" :key="m.name" class="sh-latency-item">
            <span class="sh-latency-name">{{ m.name }}</span>
            <span class="sh-latency-val" :style="{ color: m.latency < 50 ? 'var(--ar-secondary)' : 'var(--ar-primary)' }">{{ m.latency }}ms</span>
            <div class="sh-latency-bar"><div class="sh-latency-fill" :style="{ width: Math.min(m.latency, 100) + '%', background: m.latency < 50 ? 'var(--ar-secondary)' : 'var(--ar-primary)' }"></div></div>
          </div>
        </div>
      </div>

      <div class="sh-card">
        <div class="sh-section-label">GENERATION QUEUE</div>
        <div class="sh-queue">
          <div v-for="q in queue" :key="q.id" class="sh-queue-item">
            <span class="sh-queue-dot" :class="'sh-queue-dot--' + q.status"></span>
            <div class="sh-queue-info">
              <span class="sh-queue-name">{{ q.name }}</span>
              <span class="sh-queue-meta">{{ q.meta }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="sh-card">
        <div class="sh-section-label">STORAGE USAGE</div>
        <div class="sh-storage-items">
          <div v-for="s in storage" :key="s.name" class="sh-storage-row">
            <span>{{ s.name }}</span>
            <span class="sh-storage-val">{{ s.used }}</span>
            <div class="sh-storage-bar"><div class="sh-storage-fill" :style="{ width: s.pct + '%' }"></div></div>
          </div>
        </div>
      </div>

      <div class="sh-card sh-card--wide">
        <div class="sh-section-label">NODE METRICS</div>
        <div class="sh-nodes">
          <div v-for="n in nodes" :key="n.name" class="sh-node">
            <div class="sh-node-header">
              <span class="sh-node-status" :class="'sh-node-status--' + n.status"></span>
              <span class="sh-node-name">{{ n.name }}</span>
            </div>
            <div class="sh-node-val">{{ n.value }}</div>
            <div class="sh-node-label">{{ n.label }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const models = [
  { name: 'GPT-4o', latency: 45 },
  { name: 'Claude 3.5', latency: 32 },
  { name: 'Qwen-Max', latency: 28 },
  { name: 'DeepSeek-V3', latency: 55 },
]

const queue = [
  { id: 1, name: '第43章生成', meta: '进行中 · 已用 12s', status: 'active' },
  { id: 2, name: '角色分析报告', meta: '排队中 · #2', status: 'pending' },
  { id: 3, name: '世界观一致性检查', meta: '排队中 · #3', status: 'pending' },
]

const storage = [
  { name: 'Manuscripts', used: '2.1 GB', pct: 42 },
  { name: 'Resources', used: '1.8 GB', pct: 36 },
  { name: 'Vector DB', used: '0.3 GB', pct: 6 },
]

const nodes = [
  { name: 'API Server', value: '99.9%', label: 'Uptime', status: 'ok' },
  { name: 'Database', value: '12ms', label: 'Avg Response', status: 'ok' },
  { name: 'AI Engine', value: '85%', label: 'GPU Util', status: 'warn' },
  { name: 'Vector Store', value: '2.1M', label: 'Embeddings', status: 'ok' },
  { name: 'Firewall', value: 'Active', label: 'Protection', status: 'ok' },
]
</script>

<style scoped>
.sh-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.sh-header { margin-bottom: 28px; }
.sh-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.sh-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.sh-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.sh-card { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; }
.sh-card--wide { grid-column: span 2; }
.sh-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.sh-card--token { display: flex; flex-direction: column; align-items: center; text-align: center; }
.sh-token-ring { position: relative; width: 120px; height: 120px; margin: 8px 0 16px; }
.sh-ring-svg { width: 100%; height: 100%; }
.sh-ring-text { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.sh-ring-val { font-family: var(--ar-font-display); font-size: 24px; font-weight: 700; color: var(--ar-primary); }
.sh-ring-label { font-size: 11px; color: var(--ar-text-muted); }
.sh-renewal { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ar-text-secondary); }
.sh-latency-list { display: flex; flex-direction: column; gap: 12px; }
.sh-latency-item { display: grid; grid-template-columns: 100px 50px 1fr; align-items: center; gap: 12px; }
.sh-latency-name { font-size: 13px; color: var(--ar-text-primary); }
.sh-latency-val { font-family: var(--ar-font-display); font-size: 14px; font-weight: 700; text-align: right; }
.sh-latency-bar { height: 4px; background: rgba(77,70,50,0.1); border-radius: 2px; }
.sh-latency-fill { height: 100%; border-radius: 2px; }
.sh-queue { display: flex; flex-direction: column; gap: 8px; }
.sh-queue-item { display: flex; align-items: center; gap: 10px; padding: 10px; background: var(--ar-bg-elevated); border-radius: 4px; }
.sh-queue-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sh-queue-dot--active { background: var(--ar-secondary); box-shadow: 0 0 8px rgba(74,222,128,0.5); }
.sh-queue-dot--pending { background: var(--ar-text-muted); }
.sh-queue-name { font-size: 13px; font-weight: 500; color: var(--ar-text-primary); display: block; }
.sh-queue-meta { font-size: 11px; color: var(--ar-text-muted); }
.sh-storage-items { display: flex; flex-direction: column; gap: 12px; }
.sh-storage-row { display: grid; grid-template-columns: 100px 60px 1fr; align-items: center; gap: 12px; font-size: 13px; color: var(--ar-text-secondary); }
.sh-storage-val { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-text-primary); text-align: right; }
.sh-storage-bar { height: 4px; background: rgba(77,70,50,0.1); border-radius: 2px; }
.sh-storage-fill { height: 100%; background: var(--ar-secondary); border-radius: 2px; }
.sh-nodes { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.sh-node { background: var(--ar-bg-elevated); border-radius: 4px; padding: 16px; text-align: center; }
.sh-node-header { display: flex; align-items: center; justify-content: center; gap: 6px; margin-bottom: 10px; }
.sh-node-status { width: 6px; height: 6px; border-radius: 50%; }
.sh-node-status--ok { background: var(--ar-secondary); box-shadow: 0 0 6px rgba(74,222,128,0.5); }
.sh-node-status--warn { background: var(--ar-warning); box-shadow: 0 0 6px rgba(245,158,11,0.5); }
.sh-node-name { font-size: 12px; color: var(--ar-text-secondary); }
.sh-node-val { font-family: var(--ar-font-display); font-size: 22px; font-weight: 700; color: var(--ar-text-primary); }
.sh-node-label { font-size: 11px; color: var(--ar-text-muted); margin-top: 4px; }
</style>
