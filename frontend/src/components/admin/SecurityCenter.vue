<template>
  <div class="sec-root">
    <h2 class="sec-heading">FIREWALL MONITOR</h2>

    <div class="sec-stats stagger-reveal">
      <div class="sec-stat">
        <div class="sec-stat-label">Threats Blocked (24h)</div>
        <div class="sec-stat-value sec-stat-value--green">1,247</div>
      </div>
      <div class="sec-stat">
        <div class="sec-stat-label">Active Sessions</div>
        <div class="sec-stat-value">342</div>
      </div>
      <div class="sec-stat">
        <div class="sec-stat-label">Security Score</div>
        <div class="sec-stat-value sec-stat-value--primary">A+</div>
      </div>
    </div>

    <div class="sec-grid">
      <div class="sec-card">
        <div class="sec-section-label">SECURITY SETTINGS</div>
        <div class="sec-setting">
          <span>Two-Factor Authentication</span>
          <span class="sec-badge sec-badge--on">Enabled</span>
        </div>
        <div class="sec-setting">
          <span>IP Whitelist</span>
          <span class="sec-badge sec-badge--on">3 IPs</span>
        </div>
        <div class="sec-setting">
          <span>Rate Limiting</span>
          <span class="sec-badge sec-badge--on">100 req/min</span>
        </div>
        <div class="sec-setting">
          <span>CORS Policy</span>
          <span class="sec-badge">Strict</span>
        </div>
      </div>

      <div class="sec-card">
        <div class="sec-section-label">API ABUSE MONITOR</div>
        <div class="sec-abuse-chart">
          <div v-for="h in abuseData" :key="h.hour" class="sec-abuse-bar-wrapper">
            <div class="sec-abuse-bar" :style="{ height: h.pct + '%', background: h.pct > 70 ? 'var(--ar-error)' : 'var(--ar-secondary)' }"></div>
            <span class="sec-abuse-label">{{ h.hour }}</span>
          </div>
        </div>
      </div>

      <div class="sec-card sec-card--wide">
        <div class="sec-section-label">THREAT LOG</div>
        <div class="sec-threat-list">
          <div v-for="t in threats" :key="t.id" class="sec-threat">
            <span class="sec-threat-level" :class="'sec-threat-level--' + t.level"></span>
            <div class="sec-threat-info">
              <span class="sec-threat-type">{{ t.type }}</span>
              <span class="sec-threat-detail">{{ t.detail }}</span>
            </div>
            <span class="sec-threat-time">{{ t.time }}</span>
            <span class="sec-threat-action" :class="'sec-threat-action--' + t.action">{{ t.action }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const abuseData = [
  { hour: '00', pct: 15 }, { hour: '04', pct: 8 }, { hour: '08', pct: 35 },
  { hour: '12', pct: 55 }, { hour: '16', pct: 78 }, { hour: '20', pct: 42 },
]

const threats = [
  { id: 1, type: 'SQL Injection', detail: 'Blocked from 192.168.1.45', time: '2 min ago', level: 'high', action: 'blocked' },
  { id: 2, type: 'Brute Force', detail: 'Login attempts from 10.0.0.23', time: '15 min ago', level: 'high', action: 'blocked' },
  { id: 3, type: 'Rate Limit', detail: 'API abuse from token_abc123', time: '1 hour ago', level: 'medium', action: 'throttled' },
  { id: 4, type: 'Suspicious Access', detail: 'Unusual location: Minsk, BY', time: '3 hours ago', level: 'low', action: 'flagged' },
]
</script>

<style scoped>
.sec-root { padding: 4px; }
.sec-heading { font-family: var(--ar-font-display); font-size: 24px; font-weight: 700; color: var(--ar-text-primary); margin-bottom: 24px; }
.sec-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.sec-stat { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.sec-stat-label { font-size: 12px; color: var(--ar-text-muted); margin-bottom: 8px; }
.sec-stat-value { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-text-primary); }
.sec-stat-value--green { color: var(--ar-secondary); }
.sec-stat-value--primary { color: var(--ar-primary); }
.sec-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.sec-card { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.sec-card--wide { grid-column: span 2; }
.sec-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.sec-setting { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; font-size: 14px; color: var(--ar-text-secondary); }
.sec-badge { padding: 3px 10px; border-radius: 2px; font-size: 11px; font-weight: 600; background: var(--ar-bg-highlight); color: var(--ar-text-primary); }
.sec-badge--on { background: var(--ar-secondary-muted); color: var(--ar-secondary); }
.sec-abuse-chart { display: flex; align-items: flex-end; gap: 12px; height: 140px; }
.sec-abuse-bar-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; height: 100%; justify-content: flex-end; }
.sec-abuse-bar { width: 100%; border-radius: 2px 2px 0 0; }
.sec-abuse-label { font-size: 11px; color: var(--ar-text-muted); }
.sec-threat-list { display: flex; flex-direction: column; gap: 8px; }
.sec-threat { display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--ar-bg-elevated); border-radius: 4px; }
.sec-threat-level { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sec-threat-level--high { background: var(--ar-error); box-shadow: 0 0 8px rgba(239,68,68,0.5); }
.sec-threat-level--medium { background: var(--ar-warning); }
.sec-threat-level--low { background: var(--ar-text-muted); }
.sec-threat-info { flex: 1; }
.sec-threat-type { font-size: 14px; font-weight: 600; color: var(--ar-text-primary); display: block; }
.sec-threat-detail { font-size: 12px; color: var(--ar-text-muted); }
.sec-threat-time { font-size: 12px; color: var(--ar-text-muted); }
.sec-threat-action { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 2px; text-transform: uppercase; letter-spacing: 0.04em; }
.sec-threat-action--blocked { background: rgba(239,68,68,0.15); color: var(--ar-error); }
.sec-threat-action--throttled { background: rgba(245,158,11,0.15); color: var(--ar-warning); }
.sec-threat-action--flagged { background: var(--ar-bg-highlight); color: var(--ar-text-secondary); }
</style>
