<template>
  <div class="an-root">
    <div class="an-header">
      <h1 class="an-title">ANALYTICS HUB</h1>
      <p class="an-subtitle">数据分析中心 · 洞察你的创作表现</p>
    </div>

    <div class="an-stats stagger-reveal">
      <div v-for="s in stats" :key="s.label" class="an-stat-card">
        <div class="an-stat-label">{{ s.label }}</div>
        <div class="an-stat-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="an-stat-trend">{{ s.trend }}</div>
      </div>
    </div>

    <div class="an-charts">
      <div class="an-chart-card">
        <div class="an-section-label">DAILY REVENUE TREND</div>
        <div class="an-chart-placeholder">
          <div class="an-chart-bars">
            <div v-for="d in dailyData" :key="d.day" class="an-bar-col">
              <div class="an-bar" :style="{ height: d.pct + '%' }"></div>
              <span class="an-bar-label">{{ d.day }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="an-chart-card">
        <div class="an-section-label">COMMENT DENSITY HEATMAP</div>
        <div class="an-heatmap">
          <div v-for="(row, ri) in heatmap" :key="ri" class="an-heat-row">
            <div v-for="(val, ci) in row" :key="ci" class="an-heat-cell" :style="{ opacity: 0.2 + val * 0.8, background: val > 0.7 ? 'var(--ar-primary)' : 'var(--ar-secondary)' }"></div>
          </div>
        </div>
      </div>

      <div class="an-chart-card">
        <div class="an-section-label">RETENTION FUNNEL</div>
        <div class="an-funnel">
          <div v-for="f in funnel" :key="f.label" class="an-funnel-step">
            <div class="an-funnel-bar" :style="{ width: f.pct + '%' }"></div>
            <div class="an-funnel-info">
              <span>{{ f.label }}</span>
              <span class="an-funnel-val">{{ f.pct }}%</span>
            </div>
          </div>
        </div>
      </div>

      <div class="an-chart-card">
        <div class="an-section-label">DEMOGRAPHICS</div>
        <div class="an-demo-list">
          <div v-for="d in demographics" :key="d.label" class="an-demo-item">
            <span class="an-demo-label">{{ d.label }}</span>
            <div class="an-demo-bar"><div class="an-demo-fill" :style="{ width: d.pct + '%', background: d.color }"></div></div>
            <span class="an-demo-val">{{ d.pct }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const stats = [
  { label: 'Daily Revenue', value: '¥2,450', trend: '↗ +12% vs yesterday', color: 'var(--ar-primary)' },
  { label: 'Active Readers', value: '3,247', trend: '↗ +8% this week', color: 'var(--ar-secondary)' },
  { label: 'Retention Rate', value: '67%', trend: '→ stable', color: 'var(--ar-text-primary)' },
  { label: 'Avg. Reading Time', value: '24 min', trend: '↗ +3 min', color: 'var(--ar-secondary)' },
]

const dailyData = [
  { day: 'Mon', pct: 45 }, { day: 'Tue', pct: 62 }, { day: 'Wed', pct: 78 },
  { day: 'Thu', pct: 55 }, { day: 'Fri', pct: 88 }, { day: 'Sat', pct: 92 }, { day: 'Sun', pct: 70 },
]

const heatmap = [
  [0.2, 0.5, 0.8, 0.3, 0.9, 0.4, 0.7],
  [0.4, 0.7, 0.3, 0.6, 0.5, 0.8, 0.2],
  [0.6, 0.3, 0.9, 0.4, 0.7, 0.2, 0.5],
  [0.3, 0.8, 0.5, 0.9, 0.3, 0.6, 0.4],
]

const funnel = [
  { label: 'First Visit', pct: 100 },
  { label: 'Read Ch.1', pct: 72 },
  { label: 'Read Ch.5', pct: 45 },
  { label: 'Subscribed', pct: 28 },
  { label: 'Paid', pct: 15 },
]

const demographics = [
  { label: '18-24', pct: 35, color: 'var(--ar-primary)' },
  { label: '25-34', pct: 42, color: 'var(--ar-secondary)' },
  { label: '35-44', pct: 15, color: 'var(--ar-info)' },
  { label: '45+', pct: 8, color: 'var(--ar-text-muted)' },
]
</script>

<style scoped>
.an-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.an-header { margin-bottom: 28px; }
.an-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.an-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.an-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.an-stat-card { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.an-stat-label { font-size: 12px; color: var(--ar-text-muted); margin-bottom: 8px; }
.an-stat-value { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; line-height: 1; }
.an-stat-trend { font-size: 11px; color: var(--ar-text-muted); margin-top: 8px; }
.an-charts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.an-chart-card { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; }
.an-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.an-chart-bars { display: flex; align-items: flex-end; gap: 12px; height: 160px; }
.an-bar-col { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; }
.an-bar { width: 100%; background: linear-gradient(to top, var(--ar-primary), rgba(250,204,21,0.3)); border-radius: 2px 2px 0 0; transition: height 0.4s; }
.an-bar-label { font-size: 11px; color: var(--ar-text-muted); }
.an-heatmap { display: flex; flex-direction: column; gap: 4px; }
.an-heat-row { display: flex; gap: 4px; }
.an-heat-cell { width: 32px; height: 32px; border-radius: 2px; }
.an-funnel { display: flex; flex-direction: column; gap: 8px; }
.an-funnel-step { position: relative; }
.an-funnel-bar { height: 36px; background: linear-gradient(90deg, var(--ar-primary-muted), rgba(250,204,21,0.05)); border-radius: 4px; }
.an-funnel-info { position: absolute; inset: 0; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; font-size: 13px; color: var(--ar-text-primary); }
.an-funnel-val { font-family: var(--ar-font-display); font-weight: 700; }
.an-demo-list { display: flex; flex-direction: column; gap: 12px; }
.an-demo-item { display: grid; grid-template-columns: 60px 1fr 40px; align-items: center; gap: 12px; }
.an-demo-label { font-size: 13px; color: var(--ar-text-secondary); }
.an-demo-bar { height: 6px; background: rgba(77,70,50,0.1); border-radius: 3px; }
.an-demo-fill { height: 100%; border-radius: 3px; }
.an-demo-val { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-text-primary); font-size: 13px; text-align: right; }
</style>
