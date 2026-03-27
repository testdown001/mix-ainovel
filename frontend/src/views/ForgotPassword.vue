<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-4"
    style="background:#0A0A0A; font-family:'Inter',sans-serif;">

    <div class="fixed inset-0 pointer-events-none" style="background-image:linear-gradient(#161616 1px,transparent 1px),linear-gradient(90deg,#161616 1px,transparent 1px);background-size:48px 48px;opacity:0.6;"></div>
    <div class="fixed inset-0 pointer-events-none" style="background:radial-gradient(ellipse 60% 40% at 50% 0%,rgba(255,229,0,0.05) 0%,transparent 70%);"></div>

    <div class="relative w-full max-w-md">

      <!-- Logo -->
      <div class="flex items-center justify-center gap-2.5 mb-8 cursor-pointer" @click="router.push('/')">
        <div class="w-9 h-9 rounded-xl flex items-center justify-center" style="background:#FFE500;">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </div>
        <span class="text-xl font-bold text-white tracking-tight" style="font-family:'Space Grotesk',sans-serif;">Arboris Novel</span>
      </div>

      <!-- Card -->
      <div class="rounded-2xl border p-8" style="background:#111111; border-color:#222222;">

        <!-- Success state -->
        <div v-if="resetDone" class="text-center py-4">
          <div class="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-5" style="background:rgba(52,211,153,0.1); border:1px solid rgba(52,211,153,0.2);">
            <svg class="w-7 h-7" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#34D399;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <h2 class="text-xl font-bold text-white mb-2" style="font-family:'Space Grotesk',sans-serif;">密码重置成功</h2>
          <p class="text-sm mb-6" style="color:#555;">你的密码已更新，请使用新密码登录。</p>
          <button @click="router.push('/login')"
            class="w-full py-3 rounded-xl font-bold text-sm"
            style="background:#FFE500; color:#000;">
            前往登录
          </button>
        </div>

        <!-- Form state -->
        <template v-else>
          <div class="text-center mb-8">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4" style="background:#1A1A1A;">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="color:#FFE500;">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
              </svg>
            </div>
            <h1 class="text-2xl font-bold text-white mb-1.5" style="font-family:'Space Grotesk',sans-serif;">找回密码</h1>
            <p class="text-sm" style="color:#555;">输入注册邮箱，我们将发送验证码</p>
          </div>

          <form @submit.prevent="handleReset" class="space-y-4">

            <!-- Email -->
            <div>
              <label class="block text-xs font-medium mb-1.5" style="color:#888;">注册邮箱</label>
              <input v-model="email" type="email" required :disabled="codeSent"
                class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
                style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
                placeholder="your@email.com"
                @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
                @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
            </div>

            <!-- Verification code -->
            <div>
              <label class="block text-xs font-medium mb-1.5" style="color:#888;">验证码</label>
              <div class="flex gap-2">
                <input v-model="code" type="text" required
                  class="flex-1 px-4 py-3 rounded-xl text-sm transition-all outline-none"
                  style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
                  placeholder="6 位验证码"
                  @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
                  @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
                <button type="button" @click="sendCode" :disabled="countdown > 0 || sending"
                  class="flex-shrink-0 px-4 py-3 rounded-xl text-xs font-semibold transition-all whitespace-nowrap"
                  :style="countdown > 0 || sending
                    ? 'background:#1A1A1A; color:#444; border:1px solid #2A2A2A; cursor:not-allowed;'
                    : 'background:#FFE500; color:#000; border:1px solid #FFE500; cursor:pointer;'">
                  <span v-if="sending">发送中…</span>
                  <span v-else-if="countdown > 0">{{ countdown }}s 后重试</span>
                  <span v-else>发送验证码</span>
                </button>
              </div>
            </div>

            <!-- New password -->
            <div>
              <label class="block text-xs font-medium mb-1.5" style="color:#888;">新密码</label>
              <input v-model="newPassword" type="password" required
                class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
                style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
                placeholder="至少 8 位字符"
                @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
                @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
            </div>

            <!-- Confirm password -->
            <div>
              <label class="block text-xs font-medium mb-1.5" style="color:#888;">确认新密码</label>
              <input v-model="confirmPassword" type="password" required
                class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
                style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
                placeholder="再次输入新密码"
                @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
                @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
            </div>

            <!-- Error -->
            <div v-if="error" class="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
              style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.2); color:#F87171;">
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ error }}
            </div>

            <!-- Success tip -->
            <div v-if="successTip" class="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
              style="background:rgba(52,211,153,0.08); border:1px solid rgba(52,211,153,0.2); color:#34D399;">
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ successTip }}
            </div>

            <!-- Submit -->
            <button type="submit" :disabled="loading"
              class="w-full py-3.5 rounded-xl font-bold text-sm transition-all mt-2"
              style="background:#FFE500; color:#000;"
              @mouseenter="($event.currentTarget as HTMLElement).style.background='#FFF000'"
              @mouseleave="($event.currentTarget as HTMLElement).style.background='#FFE500'">
              <span v-if="loading">重置中…</span>
              <span v-else>重置密码</span>
            </button>

          </form>
        </template>

      </div>

      <!-- Back to login -->
      <p class="text-center text-sm mt-6" style="color:#555;">
        想起来了？
        <router-link to="/login" class="font-medium" style="color:#FFE500;">返回登录</router-link>
      </p>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const email = ref('');
const code = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const countdown = ref(0);
const sending = ref(false);
const loading = ref(false);
const error = ref('');
const successTip = ref('');
const codeSent = ref(false);
const resetDone = ref(false);

const sendCode = async () => {
  error.value = '';
  successTip.value = '';
  if (!email.value) { error.value = '请输入邮箱'; return; }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.value)) { error.value = '邮箱格式不正确'; return; }
  sending.value = true;
  try {
    const res = await fetch(`/api/auth/send-reset-code?email=${encodeURIComponent(email.value)}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '发送失败');
    }
    codeSent.value = true;
    successTip.value = '验证码已发送，请查收邮箱（5分钟内有效）';
    countdown.value = 60;
    const timer = setInterval(() => { countdown.value--; if (countdown.value <= 0) clearInterval(timer); }, 1000);
  } catch (err: any) {
    error.value = err.message;
  } finally {
    sending.value = false;
  }
};

const handleReset = async () => {
  error.value = '';
  successTip.value = '';
  if (newPassword.value.length < 8) { error.value = '密码至少需要8个字符'; return; }
  if (newPassword.value !== confirmPassword.value) { error.value = '两次输入的密码不一致'; return; }
  loading.value = true;
  try {
    const res = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value, code: code.value, new_password: newPassword.value })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '重置失败');
    }
    resetDone.value = true;
  } catch (err: any) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
};
</script>
