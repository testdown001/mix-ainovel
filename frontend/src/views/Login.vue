<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
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

        <!-- Tagline chip -->
        <div class="inline-flex self-start px-4 py-1.5 rounded-full border border-border text-text-secondary text-sm mb-8">
          AI创作助手 · 下一代网文引擎
        </div>

        <!-- Hero Text -->
        <h1 class="text-5xl lg:text-[56px] font-extrabold leading-[1.1] text-text-primary mb-6">
          用AI，<br>
          <span class="text-primary">释放你的故事</span>
        </h1>

        <p class="text-text-secondary text-lg leading-relaxed max-w-md mb-16">
          从灵感闪现到百万字巨著，AI全程陪伴你的创作旅程。打破写作瓶颈，让想象力不受拘束。
        </p>

        <!-- Social proof -->
        <div class="flex items-center gap-4">
          <div class="flex -space-x-2">
            <div v-for="i in 4" :key="i" class="w-8 h-8 rounded-full bg-bg-highlight border-2 border-bg-base flex items-center justify-center text-text-muted text-xs font-medium">
              {{ i }}
            </div>
          </div>
          <p class="text-text-secondary text-sm">
            超过 <span class="text-text-primary font-semibold">10,000+</span> 创作者正在使用
          </p>
        </div>
      </div>

      <!-- Right: Login Form -->
      <div class="flex justify-center lg:justify-end">
        <div class="w-full max-w-[420px]">
          <!-- Mobile Logo -->
          <div class="flex lg:hidden items-center gap-3 mb-8 justify-center">
            <div class="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-on-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
            </div>
            <span class="text-text-primary font-semibold text-xl">Arboris Novel</span>
          </div>

          <!-- Form Card -->
          <div class="bg-bg-surface border border-border rounded-2xl p-8">
            <div class="mb-8">
              <h2 class="text-2xl font-bold text-primary mb-2">欢迎回来</h2>
              <p class="text-text-secondary text-sm">登录以继续你的创作之旅</p>
            </div>

            <form @submit.prevent="handleLogin" class="space-y-5">
              <!-- Username -->
              <div>
                <label for="username" class="block text-sm font-medium text-text-secondary mb-2">账号</label>
                <div class="relative">
                  <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg class="w-5 h-5 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                    </svg>
                  </div>
                  <input
                    v-model="username"
                    id="username"
                    name="username"
                    type="text"
                    required
                    class="w-full h-12 pl-12 pr-4 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150"
                    placeholder="name@example.com"
                  />
                </div>
              </div>

              <!-- Password -->
              <div>
                <div class="flex items-center justify-between mb-2">
                  <label for="password" class="block text-sm font-medium text-text-secondary">密码</label>
                  <a href="#" class="text-sm text-primary hover:text-primary-hover transition-colors">忘记密码?</a>
                </div>
                <div class="relative">
                  <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg class="w-5 h-5 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                  </div>
                  <input
                    v-model="password"
                    id="password"
                    name="password"
                    type="password"
                    required
                    class="w-full h-12 pl-12 pr-4 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <!-- Error -->
              <div v-if="error" class="flex items-center gap-2 p-3 rounded-xl bg-error-muted">
                <svg class="w-5 h-5 flex-shrink-0 text-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-error text-sm">{{ error }}</span>
              </div>

              <!-- Submit -->
              <button
                type="submit"
                :disabled="isLoading"
                class="w-full h-12 bg-primary hover:bg-primary-hover text-on-primary font-semibold rounded-full transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center gap-2"
              >
                <svg v-if="isLoading" class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>{{ isLoading ? '正在登录...' : '登录' }}</span>
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

            <!-- Register Link -->
            <p v-if="allowRegistration" class="mt-6 text-center text-sm text-text-secondary">
              还没有账号？
              <router-link to="/register" class="text-primary font-medium hover:text-primary-hover transition-colors">
                立即注册
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
const password = ref('');
const error = ref('');
const isLoading = ref(false);
const router = useRouter();
const authStore = useAuthStore();
const allowRegistration = computed(() => authStore.allowRegistration);
const enableLinuxdoLogin = computed(() => authStore.enableLinuxdoLogin);

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
      router.push('/');
    }
  } catch (err) {
    error.value = '登录失败，请检查您的用户名和密码。';
    console.error(err);
  } finally {
    isLoading.value = false;
  }
};
</script>
