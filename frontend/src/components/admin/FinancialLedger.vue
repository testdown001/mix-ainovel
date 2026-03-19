<template>
  <div class="fl-root">
    <h2 class="fl-heading">FINANCIAL LEDGER</h2>

    <div class="fl-stats stagger-reveal">
      <div class="fl-stat">
        <div class="fl-stat-label">Revenue (MTD)</div>
        <div class="fl-stat-value fl-stat-value--primary">¥124,500</div>
        <div class="fl-stat-trend">↗ +18% vs last month</div>
      </div>
      <div class="fl-stat">
        <div class="fl-stat-label">Settled</div>
        <div class="fl-stat-value fl-stat-value--green">¥98,200</div>
        <div class="fl-stat-trend">79% of revenue</div>
      </div>
      <div class="fl-stat">
        <div class="fl-stat-label">Pending</div>
        <div class="fl-stat-value">¥26,300</div>
        <div class="fl-stat-trend">Expected in 3 days</div>
      </div>
    </div>

    <div class="fl-card">
      <div class="fl-card-header">
        <div class="fl-section-label">TRANSACTION TABLE</div>
        <div class="fl-filters">
          <select class="fl-select">
            <option>All Types</option>
            <option>Subscription</option>
            <option>Token Purchase</option>
            <option>Refund</option>
          </select>
          <button class="fl-reconcile-btn">Reconcile</button>
        </div>
      </div>

      <div class="fl-table">
        <div class="fl-thead">
          <span>Transaction ID</span>
          <span>User</span>
          <span>Type</span>
          <span>Amount</span>
          <span>Status</span>
          <span>Date</span>
        </div>
        <div v-for="t in transactions" :key="t.id" class="fl-row">
          <span class="fl-mono">{{ t.id }}</span>
          <span>{{ t.user }}</span>
          <span>{{ t.type }}</span>
          <span class="fl-amount" :class="t.amount.startsWith('-') ? 'fl-amount--neg' : ''">{{ t.amount }}</span>
          <span class="fl-status" :class="'fl-status--' + t.status">{{ t.status }}</span>
          <span class="fl-date">{{ t.date }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const transactions = [
  { id: 'TXN-2024-001', user: 'user_kai', type: 'Subscription', amount: '¥99', status: 'completed', date: '2024-03-19' },
  { id: 'TXN-2024-002', user: 'user_sara', type: 'Token Pack', amount: '¥299', status: 'completed', date: '2024-03-19' },
  { id: 'TXN-2024-003', user: 'user_doc', type: 'Refund', amount: '-¥29', status: 'processing', date: '2024-03-18' },
  { id: 'TXN-2024-004', user: 'user_neo', type: 'Subscription', amount: '¥99', status: 'completed', date: '2024-03-18' },
  { id: 'TXN-2024-005', user: 'user_zeta', type: 'Token Pack', amount: '¥29', status: 'pending', date: '2024-03-17' },
]
</script>

<style scoped>
.fl-root { padding: 4px; }
.fl-heading { font-family: var(--ar-font-display); font-size: 24px; font-weight: 700; color: var(--ar-text-primary); margin-bottom: 24px; }
.fl-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.fl-stat { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.fl-stat-label { font-size: 12px; color: var(--ar-text-muted); margin-bottom: 8px; }
.fl-stat-value { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-text-primary); }
.fl-stat-value--primary { color: var(--ar-primary); }
.fl-stat-value--green { color: var(--ar-secondary); }
.fl-stat-trend { font-size: 11px; color: var(--ar-text-muted); margin-top: 8px; }
.fl-card { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; }
.fl-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.fl-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; }
.fl-filters { display: flex; gap: 8px; }
.fl-select { padding: 6px 12px; background: var(--ar-bg-elevated); border: 1px solid rgba(77,70,50,0.15); border-radius: 4px; color: var(--ar-text-primary); font-size: 13px; outline: none; }
.fl-reconcile-btn { padding: 6px 16px; border: none; border-radius: 4px; background: var(--ar-primary); color: var(--ar-on-primary); font-size: 13px; font-weight: 600; cursor: pointer; }
.fl-table { display: flex; flex-direction: column; }
.fl-thead { display: grid; grid-template-columns: 1.5fr 1fr 1fr 0.8fr 0.8fr 1fr; gap: 12px; padding: 10px 16px; font-size: 11px; font-weight: 600; color: var(--ar-text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.fl-row { display: grid; grid-template-columns: 1.5fr 1fr 1fr 0.8fr 0.8fr 1fr; gap: 12px; padding: 12px 16px; font-size: 13px; color: var(--ar-text-secondary); border-top: 1px solid rgba(77,70,50,0.08); align-items: center; }
.fl-row:hover { background: rgba(255,255,255,0.02); }
.fl-mono { font-family: var(--ar-font-mono); font-size: 12px; color: var(--ar-text-muted); }
.fl-amount { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-text-primary); }
.fl-amount--neg { color: var(--ar-error); }
.fl-status { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 2px; text-transform: uppercase; letter-spacing: 0.04em; width: fit-content; }
.fl-status--completed { background: var(--ar-secondary-muted); color: var(--ar-secondary); }
.fl-status--processing { background: var(--ar-primary-muted); color: var(--ar-primary); }
.fl-status--pending { background: var(--ar-bg-highlight); color: var(--ar-text-muted); }
.fl-date { font-size: 12px; color: var(--ar-text-muted); }
</style>
