<!-- AIMETA P=注册页_用户注册|R=注册表单|NR=不含登录功能|E=route:/register#component:Register|X=ui|A=注册表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-4"
    style="background:#0A0A0A; font-family:'Inter',sans-serif;">

    <!-- Background subtle grid -->
    <div class="fixed inset-0 pointer-events-none" style="background-image:linear-gradient(#161616 1px,transparent 1px),linear-gradient(90deg,#161616 1px,transparent 1px);background-size:48px 48px;opacity:0.6;"></div>
    <!-- Top glow -->
    <div class="fixed inset-0 pointer-events-none" style="background:radial-gradient(ellipse 60% 40% at 50% 0%,rgba(255,229,0,0.05) 0%,transparent 70%);"></div>

    <div class="relative w-full max-w-md">

      <!-- Logo -->
      <div class="flex items-center justify-center gap-2.5 mb-8 cursor-pointer" @click="router.push('/')">
        <div class="w-9 h-9 rounded-xl flex items-center justify-center" style="background:#FFE500;">
          <svg class="w-4.5 h-4.5 w-5 h-5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </div>
        <span class="text-xl font-bold text-white tracking-tight" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
      </div>

      <!-- Card -->
      <div class="rounded-2xl border p-8" style="background:#111111; border-color:#222222;">

        <!-- Header -->
        <div class="text-center mb-8">
          <h1 class="text-2xl font-bold text-white mb-1.5" style="font-family:'Space Grotesk',sans-serif;">
            开始你的创作之旅
          </h1>
          <p class="text-sm" style="color:#666;">注册后立享 3 天创作者版完整体验</p>
        </div>

        <!-- Registration closed notice -->
        <div v-if="!allowRegistration" class="text-center py-6">
          <div class="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4" style="background:#1A1A1A;">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="color:#555;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>
            </svg>
          </div>
          <p class="font-medium text-white mb-1">暂未开放注册</p>
          <p class="text-sm mb-6" style="color:#555;">请联系管理员或稍后再试。</p>
          <router-link to="/login" class="text-sm font-medium transition-colors" style="color:#FFE500;">
            返回登录
          </router-link>
        </div>

        <!-- Registration form -->
        <form v-else @submit.prevent="handleRegister" class="space-y-4">

          <!-- Username -->
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color:#888;">用户名</label>
            <input v-model="username" type="text" required
              class="w-full px-4 py-3 rounded-xl text-sm text-white transition-all outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="至少 7 个字符或 2 个汉字"
              @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
              @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
          </div>

          <!-- Email -->
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color:#888;">邮箱</label>
            <input v-model="email" type="email" required
              class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="your@email.com"
              @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
              @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
          </div>

          <!-- Verification code -->
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color:#888;">邮箱验证码</label>
            <div class="flex gap-2">
              <input v-model="verificationCode" type="text" required
                class="flex-1 px-4 py-3 rounded-xl text-sm transition-all outline-none"
                style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
                placeholder="6 位验证码"
                @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
                @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
              <button type="button" @click="sendCode" :disabled="countdown > 0 || sending"
                class="flex-shrink-0 px-4 py-3 rounded-xl text-xs font-semibold transition-all whitespace-nowrap"
                :style="countdown > 0 || sending
                  ? 'background:#1A1A1A; color:#444; border:1px solid #2A2A2A; cursor:not-allowed;'
                  : 'background:#FFE500; color:#000; border:1px solid #FFE500; cursor:pointer;'"
                @mouseenter="(e) => { if(!(countdown > 0 || sending)) (e.currentTarget as HTMLElement).style.background='#FFF000' }"
                @mouseleave="(e) => { if(!(countdown > 0 || sending)) (e.currentTarget as HTMLElement).style.background='#FFE500' }">
                <span v-if="sending">发送中…</span>
                <span v-else-if="countdown > 0">{{ countdown }}s 后重试</span>
                <span v-else>发送验证码</span>
              </button>
            </div>
          </div>

          <!-- Password -->
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color:#888;">密码</label>
            <input v-model="password" type="password" required
              class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="至少 8 位字符"
              @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
              @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
          </div>

          <!-- Invite code (optional; prefilled from ?invite=) -->
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color:#888;">
              邀请码 <span style="color:#555;">（选填，注册双方各得积分）</span>
            </label>
            <input v-model="inviteCode" type="text"
              class="w-full px-4 py-3 rounded-xl text-sm transition-all outline-none"
              style="background:#1A1A1A; border:1px solid #2A2A2A; color:#fff;"
              placeholder="朋友分享的邀请码"
              @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
              @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'" />
          </div>

          <!-- Error message -->
          <div v-if="error" class="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
            style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.2); color:#F87171;">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            {{ error }}
          </div>

          <!-- Success message -->
          <div v-if="success" class="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
            style="background:rgba(52,211,153,0.08); border:1px solid rgba(52,211,153,0.2); color:#34D399;">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            {{ success }}
          </div>

          <!-- Turnstile CAPTCHA -->
          <div v-if="captchaEnabled" class="flex justify-center">
            <div ref="turnstileRef"></div>
          </div>

          <!-- Submit -->
          <button type="submit"
            class="w-full py-3.5 rounded-xl font-bold text-sm transition-all mt-2"
            style="background:#FFE500; color:#000;"
            @mouseenter="($event.currentTarget as HTMLElement).style.background='#FFF000'"
            @mouseleave="($event.currentTarget as HTMLElement).style.background='#FFE500'">
            免费注册
          </button>

          <!-- Terms note -->
          <p class="text-center text-xs" style="color:#444;">
            注册即表示同意
            <router-link to="/terms" class="transition-colors" style="color:#555;"
              @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
              @mouseleave="($event.target as HTMLElement).style.color='#555'">服务条款</router-link>
            与
            <router-link to="/privacy" class="transition-colors" style="color:#555;"
              @mouseenter="($event.target as HTMLElement).style.color='#FFE500'"
              @mouseleave="($event.target as HTMLElement).style.color='#555'">隐私政策</router-link>
          </p>
        </form>

      </div>

      <!-- Login link -->
      <p class="text-center text-sm mt-6" style="color:#555;">
        已有账户？
        <router-link to="/login" class="font-medium transition-colors" style="color:#FFE500;"
          @mouseenter="($event.target as HTMLElement).style.opacity='0.8'"
          @mouseleave="($event.target as HTMLElement).style.opacity='1'">
          立即登录
        </router-link>
      </p>

      <!-- Trial badge -->
      <div class="flex items-center justify-center gap-2 mt-5 text-xs" style="color:#444;">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#FFE500;"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        <span>注册免费 · 3天创作者版体验 · 无需绑卡</span>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (id: string) => void;
      remove: (id: string) => void;
    };
  }
}

const username = ref('');
const email = ref('');
const verificationCode = ref('');
const password = ref('');
const countdown = ref(0);
const sending = ref(false);
const error = ref('');
const success = ref('');
const captchaToken = ref('');
const turnstileRef = ref<HTMLElement | null>(null);
const turnstileWidgetId = ref<string | null>(null);
const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
// 邀请链接形如 /register?invite=CODE：预填但可编辑（用户也可能手输朋友发来的码）
const inviteCode = ref(typeof route.query.invite === 'string' ? route.query.invite : '');
const allowRegistration = computed(() => authStore.allowRegistration);
const captchaEnabled = computed(() => authStore.captchaEnabled);
const captchaSiteKey = computed(() => authStore.captchaSiteKey);

let turnstileScript: HTMLScriptElement | null = null;

const loadTurnstile = () => {
  if (document.getElementById('turnstile-script') || !captchaSiteKey.value) return;
  const script = document.createElement('script');
  script.id = 'turnstile-script';
  script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
  script.async = true;
  script.onload = () => renderWidget();
  document.head.appendChild(script);
  turnstileScript = script;
};

const renderWidget = () => {
  if (!window.turnstile || !turnstileRef.value || !captchaSiteKey.value) return;
  if (turnstileWidgetId.value) {
    window.turnstile.remove(turnstileWidgetId.value);
  }
  turnstileWidgetId.value = window.turnstile.render(turnstileRef.value, {
    sitekey: captchaSiteKey.value,
    theme: 'dark',
    callback: (token: string) => { captchaToken.value = token; },
    'expired-callback': () => { captchaToken.value = ''; },
    'error-callback': () => { captchaToken.value = ''; },
  });
};

watch(captchaEnabled, (val) => {
  if (val) loadTurnstile();
});

onMounted(async () => {
  try {
    await authStore.fetchAuthOptions();
  } catch (err) {
    console.error('加载认证开关失败', err);
  }
  if (!allowRegistration.value) {
    success.value = '';
    error.value = '当前已关闭注册，请稍后再试。';
  }
  if (captchaEnabled.value) {
    loadTurnstile();
  }
});

onUnmounted(() => {
  if (turnstileWidgetId.value && window.turnstile) {
    window.turnstile.remove(turnstileWidgetId.value);
  }
});

const validateInput = () => {
  if (password.value.length < 8) return '密码必须至少8个字符';
  const usernameVal = username.value;
  const hasChinese = /[\u4e00-\u9fa5]/.test(usernameVal);
  const isNumeric = /^\d+$/.test(usernameVal);
  const isAlphanumeric = /^[a-zA-Z0-9]+$/.test(usernameVal);
  if (isNumeric) return '用户名不能是纯数字';
  if (hasChinese && usernameVal.length <= 1) return '用户名长度必须大于2个汉字';
  if (isAlphanumeric && !hasChinese && usernameVal.length <= 6) return '用户名长度必须大于6个字母或数字';
  return null;
};

const sendCode = async () => {
  error.value = '';
  success.value = '';
  if (!allowRegistration.value) { error.value = '当前已关闭注册，请联系管理员。'; return; }
  if (!email.value) { error.value = '请输入邮箱'; return; }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.value)) { error.value = '邮箱格式不正确'; return; }
  sending.value = true;
  try {
    const res = await fetch(`/api/auth/send-code?email=${encodeURIComponent(email.value)}`, { method: 'POST' });
    if (!res.ok) {
      const errMsg = await res.json();
      throw new Error(errMsg.detail || '发送验证码失败');
    }
    success.value = '验证码已发送，请查收邮箱';
    countdown.value = 60;
    const timer = setInterval(() => { countdown.value--; if (countdown.value <= 0) clearInterval(timer); }, 1000);
  } catch (err: any) {
    error.value = err.message;
  } finally {
    sending.value = false;
  }
};

const handleRegister = async () => {
  error.value = '';
  success.value = '';
  const validationError = validateInput();
  if (validationError) { error.value = validationError; return; }
  if (!allowRegistration.value) { error.value = '当前已关闭注册，请联系管理员。'; return; }
  if (captchaEnabled.value && !captchaToken.value) {
    error.value = '请完成人机验证';
    return;
  }
  try {
    const body: Record<string, string> = {
      username: username.value,
      email: email.value,
      password: password.value,
      verification_code: verificationCode.value,
    };
    if (captchaToken.value) {
      body.captcha_token = captchaToken.value;
    }
    if (inviteCode.value.trim()) {
      body.invite_code = inviteCode.value.trim();
    }
    const res = await fetch('/api/auth/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const errMsg = await res.json();
      throw new Error(errMsg.detail || '注册失败');
    }
    success.value = '注册成功！即将跳转到登录页面…';
    setTimeout(() => { router.push('/login'); }, 2000);
  } catch (err: any) {
    error.value = err.message || '注册失败，请稍后再试。';
    if (turnstileWidgetId.value && window.turnstile) {
      window.turnstile.reset(turnstileWidgetId.value);
      captchaToken.value = '';
    }
    console.error(err);
  }
};
</script>
