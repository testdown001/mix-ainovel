<!-- AIMETA P=注册页_用户注册|R=注册表单|NR=不含登录功能|E=route:/register#component:Register|X=ui|A=注册表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen bg-bg-base flex items-center">
    <div class="w-full max-w-7xl mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">

      <!-- Left: Hero Content -->
      <div class="hidden lg:flex flex-col justify-center py-16">
        <!-- Logo -->
        <div class="flex items-center gap-3 mb-12">
          <div class="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
            <svg class="w-6 h-6 text-on-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
            </svg>
          </div>
          <span class="text-text-primary font-semibold text-xl">Arboris Novel</span>
        </div>

        <!-- Hero Text -->
        <h1 class="text-4xl lg:text-5xl font-extrabold leading-[1.15] text-text-primary mb-4">
          开启你的<br>
          <span class="text-primary">智能创作之旅</span>
        </h1>
        <p class="text-text-secondary text-base mb-12">Arboris Novel · AI创作助手</p>

        <!-- Feature Cards -->
        <div class="space-y-4">
          <div class="flex items-start gap-4 p-4 bg-bg-surface border border-border rounded-xl">
            <div class="w-10 h-10 bg-primary-muted rounded-lg flex items-center justify-center flex-shrink-0">
              <svg class="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
              </svg>
            </div>
            <div>
              <h3 class="text-text-primary font-semibold text-sm mb-1">AI编辑团队，全程陪伴</h3>
              <p class="text-text-muted text-xs leading-relaxed">提供专业的设定指导、大纲规划和内容润色，让创作不再孤单。</p>
            </div>
          </div>

          <div class="flex items-start gap-4 p-4 bg-bg-surface border border-border rounded-xl">
            <div class="w-10 h-10 bg-primary-muted rounded-lg flex items-center justify-center flex-shrink-0">
              <svg class="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
            </div>
            <div>
              <h3 class="text-text-primary font-semibold text-sm mb-1">章节自动生成</h3>
              <p class="text-text-muted text-xs leading-relaxed">基于设定和大纲，一键生成高质量正文，突破创作瓶颈。</p>
            </div>
          </div>

          <div class="flex items-start gap-4 p-4 bg-bg-surface border border-border rounded-xl">
            <div class="w-10 h-10 bg-primary-muted rounded-lg flex items-center justify-center flex-shrink-0">
              <svg class="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
              </svg>
            </div>
            <div>
              <h3 class="text-text-primary font-semibold text-sm mb-1">角色/世界观管理</h3>
              <p class="text-text-muted text-xs leading-relaxed">系统化管理小说设定，保持逻辑严密，避免前后矛盾。</p>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <p class="mt-12 text-text-muted text-xs">&copy; 2026 Arboris Novel. All rights reserved.</p>
      </div>

      <!-- Right: Register Form -->
      <div class="flex justify-center lg:justify-end">
        <div class="w-full max-w-[420px]">
          <!-- Mobile Logo -->
          <div class="flex lg:hidden items-center gap-3 mb-8 justify-center">
            <div class="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-on-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <span class="text-text-primary font-semibold text-xl">Arboris Novel</span>
          </div>

          <!-- Registration Closed -->
          <div v-if="!allowRegistration" class="bg-bg-surface border border-border rounded-2xl p-8 text-center">
            <h2 class="text-xl font-bold text-text-primary mb-3">暂未开放注册</h2>
            <p class="text-text-secondary text-sm mb-6">请联系管理员或稍后再试。</p>
            <router-link to="/login" class="text-primary font-medium hover:text-primary-hover transition-colors">
              返回登录
            </router-link>
          </div>

          <!-- Registration Form -->
          <div v-else class="bg-bg-surface border border-border rounded-2xl p-8">
            <div class="mb-8">
              <h2 class="text-2xl font-bold text-primary mb-2">创建账号</h2>
              <p class="text-text-secondary text-sm">加入我们，开始你的AI创作之旅</p>
            </div>

            <form @submit.prevent="handleRegister" class="space-y-5">
              <!-- Username -->
              <div>
                <label for="username" class="block text-sm font-medium text-text-secondary mb-2">用户名</label>
                <input
                  v-model="username"
                  id="username"
                  name="username"
                  type="text"
                  required
                  class="w-full h-12 px-4 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150"
                  placeholder="请输入您的用户名"
                />
              </div>

              <!-- Email -->
              <div>
                <label for="email" class="block text-sm font-medium text-text-secondary mb-2">邮箱</label>
                <input
                  v-model="email"
                  id="email"
                  name="email"
                  type="email"
                  required
                  class="w-full h-12 px-4 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150"
                  placeholder="name@example.com"
                />
              </div>

              <!-- Verification Code -->
              <div>
                <label for="verificationCode" class="block text-sm font-medium text-text-secondary mb-2">验证码</label>
                <div class="flex gap-3">
                  <input
                    v-model="verificationCode"
                    id="verificationCode"
                    name="verificationCode"
                    type="text"
                    required
                    class="flex-1 h-12 px-4 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150"
                    placeholder="输入验证码"
                  />
                  <button
                    type="button"
                    @click="sendCode"
                    :disabled="countdown > 0 || sending"
                    class="h-12 px-4 bg-bg-elevated border border-border rounded-xl text-sm font-medium text-text-primary hover:border-[rgba(255,255,255,0.2)] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-150 cursor-pointer whitespace-nowrap"
                  >
                    <span v-if="sending">发送中...</span>
                    <span v-else>{{ countdown > 0 ? countdown + 's' : '发送验证码' }}</span>
                  </button>
                </div>
              </div>

              <!-- Password -->
              <div>
                <label for="password" class="block text-sm font-medium text-text-secondary mb-2">密码</label>
                <input
                  v-model="password"
                  id="password"
                  name="password"
                  type="password"
                  required
                  class="w-full h-12 px-4 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150"
                  placeholder="至少8位字符"
                />
              </div>

              <!-- Messages -->
              <div v-if="error" class="flex items-center gap-2 p-3 rounded-xl bg-error-muted">
                <svg class="w-5 h-5 flex-shrink-0 text-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-error text-sm">{{ error }}</span>
              </div>
              <div v-if="success" class="flex items-center gap-2 p-3 rounded-xl bg-success-muted">
                <svg class="w-5 h-5 flex-shrink-0 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-success text-sm">{{ success }}</span>
              </div>

              <!-- Submit -->
              <button
                type="submit"
                class="w-full h-12 bg-primary hover:bg-primary-hover text-on-primary font-semibold rounded-full transition-all duration-150 cursor-pointer"
              >
                注册
              </button>
            </form>

            <!-- Divider -->
            <div class="relative flex items-center justify-center my-6">
              <div class="w-full h-px bg-border"></div>
              <span class="absolute px-4 bg-bg-surface text-text-muted text-sm">或者</span>
            </div>

            <!-- Social Login -->
            <div v-if="enableLinuxdoLogin">
              <a
                href="/api/auth/linuxdo/login"
                class="flex items-center justify-center gap-3 w-full h-12 bg-bg-elevated border border-border rounded-full text-text-primary font-medium hover:border-[rgba(255,255,255,0.2)] transition-all duration-150 cursor-pointer"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                使用 LinuxDO 账号登录
              </a>
            </div>

            <!-- Login Link -->
            <p class="mt-6 text-center text-sm text-text-secondary">
              已有账号？
              <router-link to="/login" class="text-primary font-medium hover:text-primary-hover transition-colors">
                立即登录
              </router-link>
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const username = ref('');
const email = ref('');
const verificationCode = ref('');
const password = ref('');
const countdown = ref(0);
const sending = ref(false);
const error = ref('');
const success = ref('');
const router = useRouter();
const authStore = useAuthStore();
const allowRegistration = computed(() => authStore.allowRegistration);
const enableLinuxdoLogin = computed(() => authStore.enableLinuxdoLogin);

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
});

const validateInput = () => {
  if (password.value.length < 8) {
    return '密码必须至少8个字符';
  }
  const usernameVal = username.value;
  const hasChinese = /[\u4e00-\u9fa5]/.test(usernameVal);
  const isNumeric = /^\d+$/.test(usernameVal);
  const isAlphanumeric = /^[a-zA-Z0-9]+$/.test(usernameVal);
  if (isNumeric) {
    return '用户名不能是纯数字';
  }
  if (hasChinese && usernameVal.length <= 1) {
    return '用户名长度必须大于2个汉字';
  }
  if (isAlphanumeric && !hasChinese && usernameVal.length <= 6) {
    return '用户名长度必须大于6个字母或数字';
  }
  return null;
};

const sendCode = async () => {
  error.value = '';
  success.value = '';
  if (!allowRegistration.value) {
    error.value = '当前已关闭注册，请联系管理员。';
    return;
  }
  if (!email.value) {
    error.value = '请输入邮箱';
    return;
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.value)) {
    error.value = '邮箱格式不正确';
    return;
  }
  sending.value = true;
  try {
    const res = await fetch(`/api/auth/send-code?email=${encodeURIComponent(email.value)}`, {
      method: 'POST'
    });
    if (!res.ok) {
      const errMsg = await res.json();
      throw new Error(errMsg.detail || '发送验证码失败');
    }
    success.value = '验证码已发送，请查收邮箱';
    countdown.value = 60;
    const timer = setInterval(() => {
      countdown.value--;
      if (countdown.value <= 0) clearInterval(timer);
    }, 1000);
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
  if (validationError) {
    error.value = validationError;
    return;
  }
  if (!allowRegistration.value) {
    error.value = '当前已关闭注册，请联系管理员。';
    return;
  }
  try {
    const res = await fetch('/api/auth/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username.value,
        email: email.value,
        password: password.value,
        verification_code: verificationCode.value
      })
    });
    if (!res.ok) {
      const errMsg = await res.json();
      throw new Error(errMsg.detail || '注册失败');
    }
    success.value = '注册成功！正在跳转到登录页面...';
    setTimeout(() => {
      router.push('/login');
    }, 2000);
  } catch (err: any) {
    error.value = err.message || '注册失败，请稍后再试。';
    console.error(err);
  }
};
</script>
