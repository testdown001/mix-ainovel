<template>
  <div class="rc-root">
    <div class="rc-banner">
      <div class="rc-banner-content">
        <h2 class="rc-banner-title">升级为 Premium，释放 AI 全部创作力</h2>
        <p class="rc-banner-desc">无限 Token · 优先生成 · 高级模型访问</p>
      </div>
    </div>

    <div class="rc-header">
      <h1 class="rc-title">RECHARGE CENTER</h1>
      <p class="rc-subtitle">Token 充值与订阅管理</p>
    </div>

    <div class="rc-body">
      <div class="rc-main">
        <div class="rc-section-label">TOKEN PACKAGES</div>
        <div class="rc-packages">
          <div v-for="p in packages" :key="p.id" class="rc-package" :class="{ 'rc-package--featured': p.featured }" @click="selectedPkg = p.id">
            <div v-if="p.featured" class="rc-package-badge">MOST POPULAR</div>
            <div class="rc-package-name">{{ p.name }}</div>
            <div class="rc-package-price">¥{{ p.price }}</div>
            <div class="rc-package-tokens">{{ p.tokens.toLocaleString() }} Tokens</div>
            <ul class="rc-package-features">
              <li v-for="f in p.features" :key="f">{{ f }}</li>
            </ul>
            <button class="rc-package-btn" :class="{ 'rc-package-btn--active': selectedPkg === p.id }">
              {{ selectedPkg === p.id ? '已选择' : '选择方案' }}
            </button>
          </div>
        </div>

        <div class="rc-section-label" style="margin-top:28px;">PAYMENT METHOD</div>
        <div class="rc-payments">
          <button v-for="m in methods" :key="m" class="rc-pay-method" :class="{ 'rc-pay-method--active': payMethod === m }" @click="payMethod = m">{{ m }}</button>
        </div>
      </div>

      <div class="rc-sidebar">
        <div class="rc-summary">
          <div class="rc-section-label">ORDER SUMMARY</div>
          <div class="rc-sum-row"><span>Selected Plan</span><span>{{ selectedPackage?.name }}</span></div>
          <div class="rc-sum-row"><span>Tokens</span><span>{{ selectedPackage?.tokens.toLocaleString() }}</span></div>
          <div class="rc-sum-divider"></div>
          <div class="rc-sum-row rc-sum-total"><span>Total</span><span>¥{{ selectedPackage?.price }}</span></div>
          <button class="rc-checkout-btn">确认支付</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const selectedPkg = ref(2)
const payMethod = ref('微信支付')
const methods = ['微信支付', '支付宝', 'Apple Pay']

const packages = [
  { id: 1, name: 'Basic', price: 29, tokens: 50000, featured: false, features: ['基础模型访问', '标准生成速度', '5GB 存储'] },
  { id: 2, name: 'Pro', price: 99, tokens: 200000, featured: true, features: ['高级模型访问', '优先生成', '20GB 存储', 'Plot Lab 解锁'] },
  { id: 3, name: 'Enterprise', price: 299, tokens: 1000000, featured: false, features: ['全部模型', '最高优先级', '无限存储', '全功能解锁', 'API 访问'] },
]

const selectedPackage = computed(() => packages.find(p => p.id === selectedPkg.value))
</script>

<style scoped>
.rc-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.rc-banner { background: linear-gradient(135deg, rgba(250,204,21,0.12), rgba(74,222,128,0.08)); border-radius: 4px; padding: 28px 32px; margin-bottom: 28px; border-left: 3px solid var(--ar-primary); }
.rc-banner-title { font-family: var(--ar-font-display); font-size: 22px; font-weight: 700; color: var(--ar-primary); margin-bottom: 4px; }
.rc-banner-desc { font-size: 14px; color: var(--ar-text-secondary); }
.rc-header { margin-bottom: 28px; }
.rc-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.rc-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.rc-body { display: grid; grid-template-columns: 1fr 320px; gap: 24px; }
.rc-main {}
.rc-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.rc-packages { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.rc-package { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; border: 1px solid rgba(77,70,50,0.1); position: relative; transition: all 0.2s; cursor: pointer; }
.rc-package:hover { border-color: rgba(77,70,50,0.3); }
.rc-package--featured { border-color: var(--ar-primary); box-shadow: 0 0 30px rgba(250,204,21,0.08); }
.rc-package-badge { position: absolute; top: -1px; right: 16px; padding: 4px 10px; background: var(--ar-primary); color: var(--ar-on-primary); font-size: 9px; font-weight: 700; letter-spacing: 0.08em; border-radius: 0 0 4px 4px; }
.rc-package-name { font-family: var(--ar-font-display); font-size: 18px; font-weight: 700; color: var(--ar-text-primary); margin-bottom: 8px; }
.rc-package-price { font-family: var(--ar-font-display); font-size: 32px; font-weight: 700; color: var(--ar-primary); margin-bottom: 4px; }
.rc-package-tokens { font-size: 13px; color: var(--ar-text-secondary); margin-bottom: 16px; }
.rc-package-features { list-style: none; padding: 0; margin: 0 0 20px; }
.rc-package-features li { font-size: 13px; color: var(--ar-text-secondary); padding: 4px 0; }
.rc-package-features li::before { content: '✓'; margin-right: 8px; color: var(--ar-secondary); }
.rc-package-btn { width: 100%; padding: 10px; border: 1px solid rgba(77,70,50,0.3); border-radius: 4px; background: transparent; color: var(--ar-text-primary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.rc-package-btn--active { background: var(--ar-primary); color: var(--ar-on-primary); border-color: var(--ar-primary); }
.rc-payments { display: flex; gap: 8px; }
.rc-pay-method { padding: 10px 20px; border: 1px solid rgba(77,70,50,0.2); border-radius: 4px; background: var(--ar-bg-surface); color: var(--ar-text-secondary); font-size: 13px; cursor: pointer; transition: all 0.15s; }
.rc-pay-method--active { border-color: var(--ar-primary); color: var(--ar-primary); background: var(--ar-primary-muted); }
.rc-sidebar {}
.rc-summary { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; position: sticky; top: 80px; }
.rc-sum-row { display: flex; justify-content: space-between; font-size: 14px; color: var(--ar-text-secondary); padding: 8px 0; }
.rc-sum-total { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-primary); font-size: 18px; }
.rc-sum-divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(77,70,50,0.15), transparent); margin: 8px 0; }
.rc-checkout-btn { width: 100%; padding: 14px; border: none; border-radius: 4px; background: var(--ar-primary); color: var(--ar-on-primary); font-size: 15px; font-weight: 700; cursor: pointer; margin-top: 16px; transition: all 0.15s; }
.rc-checkout-btn:hover { box-shadow: 0 0 24px rgba(250,204,21,0.35); }
</style>
