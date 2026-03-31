<!-- AIMETA P=灵感加载_加载动画组件|R=加载动画|NR=不含业务逻辑|E=component:InspirationLoading|X=internal|A=加载组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="loading-root">
    <div class="loading-glow-wrap">
      <div class="loading-orb">
        <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color:#fff;">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
        </svg>
      </div>
      <div class="loading-ring"></div>
    </div>

    <h2 class="loading-title">正在为你准备灵感空间...</h2>

    <div class="loading-steps">
      <div class="loading-step" style="animation-delay:0.1s">
        <span class="step-dot" style="background:#FFE500;"></span>
        <span>连接文思泉涌的AI...</span>
      </div>
      <div class="loading-step" style="animation-delay:0.4s">
        <span class="step-dot" style="background:#C084FC;"></span>
        <span>铺开创意的画卷...</span>
      </div>
      <div class="loading-step" style="animation-delay:0.7s">
        <span class="step-dot" style="background:#2ED573;"></span>
        <span>准备开启灵感之旅!</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.loading-root {
  position: absolute;
  inset: 0;
  background: #0A0A0A;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
}

.loading-glow-wrap {
  position: relative;
  width: 80px;
  height: 80px;
  margin-bottom: 2rem;
}

.loading-orb {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FFE500 0%, #C084FC 50%, #4F46E5 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: orb-breathe 2s ease-in-out infinite;
  box-shadow: 0 0 40px rgba(192, 132, 252, 0.3), 0 0 80px rgba(255, 229, 0, 0.15);
}

.loading-ring {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #FFE500;
  border-right-color: #C084FC;
  animation: ring-spin 1.5s linear infinite;
}

.loading-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #EEEEEE;
  margin-bottom: 1.5rem;
  letter-spacing: 0.02em;
}

.loading-steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.loading-step {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: #888888;
  opacity: 0;
  animation: step-appear 0.5s ease forwards;
}

.step-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  animation: dot-pulse 1.8s ease-in-out infinite;
}

@keyframes orb-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
}

@keyframes ring-spin {
  to { transform: rotate(360deg); }
}

@keyframes step-appear {
  to { opacity: 1; }
}

@keyframes dot-pulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.4); }
}
</style>
