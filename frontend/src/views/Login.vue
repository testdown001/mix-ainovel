<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
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

        <div class="text-center mb-8">
          <h1 class="text-2xl font-bold text-white mb-1.5" style="font-family:'Space Grotesk',sans-serif;">欢迎回来</h1>
          <p class="text-sm" style="color:#555;">登录以继续你的创作之旅</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-4">

          <!-- Username -->
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color:#888;">用户名</label>
            <input v-model="username" type="text" required
              class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="请输入用户名"
              @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
              @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
          </div>

          <!-- Password -->
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="text-xs font-medium" style="color:#888;">密码</label>
              <router-link to="/forgot-password" class="text-xs transition-colors" style="color:#555;"
                @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
                @mouseleave="($event.target as HTMLElement).style.color='#555'">
                忘记密码？
              </router-link>
            </div>
            <input v-model="password" type="password" required
              class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="请输入密码"
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

          <!-- Submit -->
          <button type="submit" :disabled="isLoading"
            class="w-full py-3.5 rounded-xl font-bold text-sm transition-all mt-2 flex items-center justify-center gap-2"
            style="background:#FFE500; color:#000;"
            @mouseenter="(e) => { if (!isLoading) (e.currentTarget as HTMLElement).style.background='#FFF000' }"
            @mouseleave="(e) => { if (!isLoading) (e.currentTarget as HTMLElement).style.background='#FFE500' }">
            <svg v-if="isLoading" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
            </svg>
            <span>{{ isLoading ? '登录中…' : '登录' }}</span>
          </button>

        </form>

        <!-- 手机号验证码登录 -->
        <div v-if="enablePhoneLogin" class="mt-6">
          <div class="relative flex items-center my-4">
            <div class="flex-1" style="height:1px; background:#1E1E1E;"></div>
            <span class="px-3 text-xs" style="color:#444;">手机号快捷登录</span>
            <div class="flex-1" style="height:1px; background:#1E1E1E;"></div>
          </div>
          <div class="space-y-3">
            <input v-model="phone" type="tel" maxlength="11"
              class="w-full px-4 py-3 rounded-xl text-sm outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="请输入手机号" />
            <div class="flex gap-2">
              <input v-model="phoneCode" type="text" maxlength="6"
                class="flex-1 px-4 py-3 rounded-xl text-sm outline-none"
                style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
                placeholder="短信验证码" />
              <button type="button" :disabled="codeCountdown > 0 || isLoading" @click="handleSendCode"
                class="px-4 rounded-xl text-sm whitespace-nowrap"
                style="background:#1A1A1A; border:1px solid #2A2A2A; color:#FFE500;">
                {{ codeCountdown > 0 ? `${codeCountdown}s` : '获取验证码' }}
              </button>
            </div>
            <button type="button" :disabled="isLoading" @click="handlePhoneLogin"
              class="w-full py-3 rounded-xl font-bold text-sm"
              style="background:#1A1A1A; border:1px solid #FFE50055; color:#FFE500;">
              手机号登录 / 注册
            </button>
          </div>
        </div>

        <!-- 第三方登录 -->
        <div v-if="enableLinuxdoLogin || enableWechatLogin || enableGoogleLogin">
          <div class="relative flex items-center my-6">
            <div class="flex-1" style="height:1px; background:#1E1E1E;"></div>
            <span class="px-3 text-xs" style="color:#444;">或使用第三方账号</span>
            <div class="flex-1" style="height:1px; background:#1E1E1E;"></div>
          </div>
          <div class="space-y-2.5">
            <a v-if="enableWechatLogin" href="/api/auth/wechat/login"
              class="flex items-center justify-center gap-2.5 w-full py-3 rounded-xl text-sm font-medium transition-all"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#07C160;">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8.5 4C4.36 4 1 6.91 1 10.5c0 2.05 1.1 3.88 2.83 5.07L3 18l2.7-1.36c.9.25 1.86.36 2.8.36.24 0 .47 0 .7-.03A6.3 6.3 0 018 14.5C8 10.91 11.58 8 16 8c.27 0 .54.01.8.04C16.1 5.7 12.66 4 8.5 4z"/></svg>
              使用微信登录
            </a>
            <a v-if="enableGoogleLogin" href="/api/auth/google/login"
              class="flex items-center justify-center gap-2.5 w-full py-3 rounded-xl text-sm font-medium transition-all"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#888;">
              <svg class="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.5 12.2c0-.7-.06-1.4-.18-2H12v3.8h5.9a5 5 0 01-2.2 3.3v2.7h3.6c2.1-2 3.2-4.9 3.2-7.8z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.6-2.7c-1 .67-2.28 1.06-3.68 1.06-2.83 0-5.23-1.9-6.08-4.48H2.18v2.8A11 11 0 0012 23z"/><path fill="#FBBC05" d="M5.92 14.2a6.6 6.6 0 010-4.2v-2.8H2.18a11 11 0 000 9.8l3.74-2.8z"/><path fill="#EA4335" d="M12 5.4c1.62 0 3.06.56 4.2 1.64l3.15-3.15C17.45 2.1 14.97 1 12 1A11 11 0 002.18 7.2L5.92 10c.85-2.58 3.25-4.6 6.08-4.6z"/></svg>
              使用谷歌登录
            </a>
            <a v-if="enableLinuxdoLogin" href="/api/auth/linuxdo/login"
              class="flex items-center justify-center gap-2.5 w-full py-3 rounded-xl text-sm font-medium transition-all"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#888;">
              <svg class="w-4 h-4" aria-hidden="true" viewBox="0 0 496 512">
                <path fill="currentColor" d="M248 8C111 8 0 119 0 256s111 248 248 248 248-111 248-248S385 8 248 8zm0 448c-110.5 0-200-89.5-200-200S137.5 56 248 56s200 89.5 200 200-89.5 200-200 200z"/>
              </svg>
              使用 Linux DO 登录
            </a>
          </div>
        </div>

        <!-- Register -->
        <p v-if="allowRegistration" class="text-center text-sm mt-6" style="color:#555;">
          还没有账户？
          <router-link to="/register" class="font-medium" style="color:#FFE500;">
            免费注册
          </router-link>
        </p>

      </div>

      <!-- Footer note -->
      <p class="text-center text-xs mt-6" style="color:#333;">
        登录即表示同意
        <router-link to="/terms" class="transition-colors" style="color:#444;"
          @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
          @mouseleave="($event.target as HTMLElement).style.color='#444'">服务条款</router-link>
        与
        <router-link to="/privacy" class="transition-colors" style="color:#444;"
          @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
          @mouseleave="($event.target as HTMLElement).style.color='#444'">隐私政策</router-link>
      </p>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const username = ref('');
const password = ref('');
const error = ref('');
const isLoading = ref(false);
const phone = ref('');
const phoneCode = ref('');
const codeCountdown = ref(0);
let countdownTimer: ReturnType<typeof setInterval> | null = null;
const router = useRouter();
const authStore = useAuthStore();
const allowRegistration = computed(() => authStore.allowRegistration);
const enableLinuxdoLogin = computed(() => authStore.enableLinuxdoLogin);
const enableWechatLogin = computed(() => authStore.enableWechatLogin);
const enableGoogleLogin = computed(() => authStore.enableGoogleLogin);
const enablePhoneLogin = computed(() => authStore.enablePhoneLogin);

const handleSendCode = async () => {
  error.value = '';
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    error.value = '请输入正确的手机号';
    return;
  }
  try {
    await authStore.sendPhoneCode(phone.value);
    codeCountdown.value = 60;
    countdownTimer = setInterval(() => {
      codeCountdown.value -= 1;
      if (codeCountdown.value <= 0 && countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
      }
    }, 1000);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '验证码发送失败';
  }
};

const handlePhoneLogin = async () => {
  error.value = '';
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    error.value = '请输入正确的手机号';
    return;
  }
  if (!phoneCode.value.trim()) {
    error.value = '请输入验证码';
    return;
  }
  isLoading.value = true;
  try {
    await authStore.phoneLogin(phone.value, phoneCode.value.trim());
    router.push('/home');
  } catch (err) {
    error.value = err instanceof Error ? err.message : '手机号登录失败';
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  authStore.fetchAuthOptions().catch((err) => {
    console.error('初始化认证配置失败', err);
  });
});

const handleLogin = async () => {
  error.value = '';
  isLoading.value = true;
  try {
    const mustChange = await authStore.login(username.value, password.value);
    const user = authStore.user;
    if (user?.is_admin && (authStore.mustChangePassword || mustChange)) {
      router.push({ name: 'admin', query: { tab: 'password' } });
    } else {
      router.push('/home');
    }
  } catch (err) {
    error.value = '登录失败，请检查用户名和密码。';
    console.error(err);
  } finally {
    isLoading.value = false;
  }
};
</script>
