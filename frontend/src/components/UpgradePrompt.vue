<!-- AIMETA P=升级引导弹窗_402积分不足与403档位不足的统一转化入口|R=错误转化为升级动线|NR=不含支付逻辑|E=component:UpgradePrompt|X=ui|A=转化组件|D=vue|S=dom -->
<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center"
    style="background:rgba(0,0,0,0.7);" @click.self="$emit('close')">
    <div class="rounded-2xl border p-8 max-w-sm w-full mx-4 text-center"
      style="background:#141414; border-color:#2A2A2A;">
      <div class="w-12 h-12 rounded-xl mx-auto mb-4 flex items-center justify-center"
        style="background:rgba(255,229,0,0.1);">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;">
          <path v-if="kind === 'credits'" stroke-linecap="round" stroke-linejoin="round"
            d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          <path v-else stroke-linecap="round" stroke-linejoin="round"
            d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
        </svg>
      </div>
      <h3 class="text-lg font-bold text-white mb-2">
        {{ kind === 'credits' ? '积分不足' : '需要更高档位' }}
      </h3>
      <p class="text-sm mb-6 leading-relaxed" style="color:#888888;">{{ message }}</p>
      <div class="space-y-2.5">
        <button @click="goSubscription"
          class="w-full py-2.5 rounded-lg font-semibold text-sm"
          style="background:#FFE500; color:#000;">
          {{ kind === 'credits' ? '升级套餐获取更多积分' : '查看升级方案' }}
        </button>
        <button v-if="kind === 'credits'" @click="goCredits"
          class="w-full py-2.5 rounded-lg font-semibold text-sm"
          style="background:transparent; border:1px solid #2A2A2A; color:#CCCCCC;">
          查看积分明细
        </button>
        <button @click="$emit('close')"
          class="w-full py-2.5 rounded-lg font-semibold text-sm"
          style="background:transparent; border:1px solid #2A2A2A; color:#888888;">
          暂不
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{
  show: boolean
  /** credits = 402 积分不足；tier = 403 档位/模型门控 */
  kind: 'credits' | 'tier'
  message: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()
const router = useRouter()

const goSubscription = () => {
  emit('close')
  router.push('/settings?tab=subscription')
}
const goCredits = () => {
  emit('close')
  router.push('/settings?tab=credits')
}
</script>
