<template>
  <div class="tm-root">
    <h2 class="tm-heading">TRANSACTIONS & QUOTAS</h2>

    <div class="tm-grid">
      <div class="tm-card">
        <div class="tm-section-label">USER QUOTA CONTROL</div>
        <div class="tm-quota-list">
          <div v-for="u in users" :key="u.name" class="tm-quota-item">
            <div class="tm-quota-user">
              <div class="tm-avatar">{{ u.name.charAt(0) }}</div>
              <div>
                <div class="tm-quota-name">{{ u.name }}</div>
                <div class="tm-quota-tier">{{ u.tier }}</div>
              </div>
            </div>
            <div class="tm-quota-bar-wrap">
              <div class="tm-quota-bar"><div class="tm-quota-fill" :style="{ width: u.used + '%' }"></div></div>
              <span class="tm-quota-text">{{ u.used }}% used</span>
            </div>
            <div class="tm-quota-actions">
              <button class="tm-action-btn">Adjust</button>
              <button class="tm-action-btn tm-action-btn--warn">Reset</button>
            </div>
          </div>
        </div>
      </div>

      <div class="tm-card">
        <div class="tm-section-label">SUBSCRIPTION PLANS</div>
        <div class="tm-plans">
          <div v-for="p in plans" :key="p.name" class="tm-plan">
            <div class="tm-plan-header">
              <span class="tm-plan-name">{{ p.name }}</span>
              <span class="tm-plan-price">¥{{ p.price }}/mo</span>
            </div>
            <div class="tm-plan-stats">
              <span>{{ p.subscribers }} subscribers</span>
              <span>MRR: ¥{{ (p.subscribers * p.price).toLocaleString() }}</span>
            </div>
            <div class="tm-plan-bar"><div class="tm-plan-fill" :style="{ width: (p.subscribers / 100 * 100) + '%', maxWidth: '100%' }"></div></div>
          </div>
        </div>
      </div>

      <div class="tm-card tm-card--wide">
        <div class="tm-section-label">RECENT TRANSACTIONS</div>
        <div class="tm-txn-list">
          <div v-for="t in transactions" :key="t.id" class="tm-txn">
            <span class="tm-txn-id">{{ t.id }}</span>
            <span class="tm-txn-user">{{ t.user }}</span>
            <span class="tm-txn-desc">{{ t.desc }}</span>
            <span class="tm-txn-amount" :class="t.amount > 0 ? 'tm-txn-amount--pos' : 'tm-txn-amount--neg'">
              {{ t.amount > 0 ? '+' : '' }}{{ t.amount }} tokens
            </span>
            <span class="tm-txn-time">{{ t.time }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const users = [
  { name: 'Kai Chen', tier: 'Pro', used: 72 },
  { name: 'Sara Wang', tier: 'Enterprise', used: 45 },
  { name: 'Dr. Neo', tier: 'Basic', used: 95 },
  { name: 'Zeta Liu', tier: 'Pro', used: 30 },
]

const plans = [
  { name: 'Basic', price: 29, subscribers: 45 },
  { name: 'Pro', price: 99, subscribers: 78 },
  { name: 'Enterprise', price: 299, subscribers: 12 },
]

const transactions = [
  { id: '#TXN-001', user: 'kai_chen', desc: 'Token purchase (Pro)', amount: 200000, time: '5 min ago' },
  { id: '#TXN-002', user: 'sara_wang', desc: 'Generation: Ch.42', amount: -3200, time: '12 min ago' },
  { id: '#TXN-003', user: 'dr_neo', desc: 'Token purchase (Basic)', amount: 50000, time: '1 hour ago' },
  { id: '#TXN-004', user: 'zeta_liu', desc: 'Plot Lab analysis', amount: -8500, time: '2 hours ago' },
]
</script>

<style scoped>
.tm-root { padding: 4px; }
.tm-heading { font-family: var(--ar-font-display); font-size: 24px; font-weight: 700; color: var(--ar-text-primary); margin-bottom: 24px; }
.tm-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.tm-card { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; }
.tm-card--wide { grid-column: span 2; }
.tm-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.tm-quota-list { display: flex; flex-direction: column; gap: 14px; }
.tm-quota-item { display: flex; align-items: center; gap: 16px; }
.tm-quota-user { display: flex; align-items: center; gap: 10px; min-width: 140px; }
.tm-avatar { width: 32px; height: 32px; border-radius: 4px; background: var(--ar-bg-highlight); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; color: var(--ar-primary); flex-shrink: 0; }
.tm-quota-name { font-size: 14px; font-weight: 600; color: var(--ar-text-primary); }
.tm-quota-tier { font-size: 11px; color: var(--ar-text-muted); }
.tm-quota-bar-wrap { flex: 1; display: flex; align-items: center; gap: 8px; }
.tm-quota-bar { flex: 1; height: 4px; background: rgba(77,70,50,0.1); border-radius: 2px; }
.tm-quota-fill { height: 100%; background: var(--ar-secondary); border-radius: 2px; }
.tm-quota-text { font-size: 12px; color: var(--ar-text-muted); min-width: 60px; }
.tm-quota-actions { display: flex; gap: 6px; }
.tm-action-btn { padding: 4px 12px; border: 1px solid rgba(77,70,50,0.2); border-radius: 4px; background: transparent; color: var(--ar-text-secondary); font-size: 12px; cursor: pointer; transition: all 0.15s; }
.tm-action-btn:hover { border-color: var(--ar-primary); color: var(--ar-primary); }
.tm-action-btn--warn:hover { border-color: var(--ar-error); color: var(--ar-error); }
.tm-plans { display: flex; flex-direction: column; gap: 14px; }
.tm-plan { padding: 14px; background: var(--ar-bg-elevated); border-radius: 4px; }
.tm-plan-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.tm-plan-name { font-family: var(--ar-font-display); font-size: 16px; font-weight: 700; color: var(--ar-text-primary); }
.tm-plan-price { font-family: var(--ar-font-display); font-size: 16px; font-weight: 700; color: var(--ar-primary); }
.tm-plan-stats { display: flex; justify-content: space-between; font-size: 12px; color: var(--ar-text-muted); margin-bottom: 8px; }
.tm-plan-bar { height: 3px; background: rgba(77,70,50,0.1); border-radius: 2px; }
.tm-plan-fill { height: 100%; background: var(--ar-primary); border-radius: 2px; }
.tm-txn-list { display: flex; flex-direction: column; gap: 6px; }
.tm-txn { display: grid; grid-template-columns: 100px 100px 1fr 120px 100px; gap: 12px; padding: 10px 12px; font-size: 13px; color: var(--ar-text-secondary); align-items: center; border-radius: 4px; }
.tm-txn:hover { background: rgba(255,255,255,0.02); }
.tm-txn-id { font-family: var(--ar-font-mono); font-size: 11px; color: var(--ar-text-muted); }
.tm-txn-user { font-weight: 500; color: var(--ar-text-primary); }
.tm-txn-amount { font-family: var(--ar-font-display); font-weight: 700; text-align: right; }
.tm-txn-amount--pos { color: var(--ar-secondary); }
.tm-txn-amount--neg { color: var(--ar-text-muted); }
.tm-txn-time { font-size: 12px; color: var(--ar-text-muted); text-align: right; }
</style>
