<!-- AIMETA P=邀请返积分面板_邀请链接与统计|R=邀请码展示_复制_统计|NR=不含发放逻辑|E=component:ReferralPanel|X=ui|A=面板组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="rounded-xl p-6" style="background: #141414; border: 1px solid #2A2A2A;">
    <div class="flex items-center justify-between mb-1">
      <h2 class="text-lg font-bold text-white" style="font-family: 'Space Grotesk', sans-serif;">邀请返积分</h2>
      <span v-if="info && !info.enabled" class="text-xs px-2 py-1 rounded" style="background:#2A2A2A; color:#888;">暂未开放</span>
    </div>
    <p class="text-sm mb-6" style="color: #888;">
      好友通过你的链接注册，双方各得积分——入永久池，不随月度重置清零。
    </p>

    <div v-if="loading" class="py-8 text-center text-sm" style="color:#666;">加载中…</div>
    <div v-else-if="error" class="py-4 text-sm" style="color:#F87171;">{{ error }}</div>

    <template v-else-if="info">
      <!-- 奖励规则 -->
      <div class="grid grid-cols-3 gap-3 mb-6">
        <div class="rounded-lg p-4 text-center" style="background:#1A1A1A; border:1px solid #2A2A2A;">
          <div class="text-xl font-bold" style="color:#FFE500;">+{{ info.inviter_credits }}</div>
          <div class="text-xs mt-1" style="color:#888;">每邀请一位，你得</div>
        </div>
        <div class="rounded-lg p-4 text-center" style="background:#1A1A1A; border:1px solid #2A2A2A;">
          <div class="text-xl font-bold" style="color:#FFE500;">+{{ info.invitee_credits }}</div>
          <div class="text-xs mt-1" style="color:#888;">好友注册即得</div>
        </div>
        <div class="rounded-lg p-4 text-center" style="background:#1A1A1A; border:1px solid #2A2A2A;">
          <div class="text-xl font-bold text-white">{{ info.invited_count }}<span class="text-sm" style="color:#666;"> / {{ info.max_invites }}</span></div>
          <div class="text-xs mt-1" style="color:#888;">已邀请 · 累计 +{{ info.credits_earned }}</div>
        </div>
      </div>

      <!-- 邀请链接 -->
      <label class="block text-xs font-medium mb-1.5" style="color:#888;">我的邀请链接</label>
      <div class="flex gap-2">
        <input :value="inviteUrl" readonly
          class="flex-1 px-4 py-3 rounded-xl text-sm outline-none"
          style="background:#1A1A1A; border:1px solid #2A2A2A; color:#ccc;" />
        <button type="button" @click="copyLink"
          class="flex-shrink-0 px-5 py-3 rounded-xl text-sm font-semibold transition-all"
          style="background:#FFE500; color:#000;">
          {{ copied ? '已复制' : '复制链接' }}
        </button>
      </div>
      <p class="text-xs mt-2" style="color:#555;">
        邀请码：{{ info.invite_code }}（好友在注册页手动填写同样有效）
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { creditsApi, type ReferralInfo } from '@/api/credits'

const info = ref<ReferralInfo | null>(null)
const loading = ref(true)
const error = ref('')
const copied = ref(false)

const inviteUrl = computed(() =>
  info.value ? `${window.location.origin}/register?invite=${info.value.invite_code}` : '',
)

const copyLink = async () => {
  if (!inviteUrl.value) return
  try {
    await navigator.clipboard.writeText(inviteUrl.value)
  } catch {
    // 剪贴板 API 不可用（http 环境等）：退回选中文本让用户手动复制
    const input = document.querySelector<HTMLInputElement>('input[readonly]')
    input?.select()
    document.execCommand('copy')
  }
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

onMounted(async () => {
  try {
    info.value = await creditsApi.getReferralInfo()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>
