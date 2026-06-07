// AIMETA P=认证状态_用户登录状态管理|R=token_user_login_logout|NR=不含API调用|E=store:auth|X=internal|A=useAuthStore|D=pinia|S=storage|RD=./README.ai
import { defineStore } from 'pinia';

const API_URL = `/api/auth`;

interface AuthOptions {
  allow_registration: boolean;
  enable_linuxdo_login: boolean;
  enable_wechat_login?: boolean;
  enable_google_login?: boolean;
  enable_phone_login?: boolean;
  captcha_enabled: boolean;
  captcha_site_key: string | null;
}

// Helper function to handle fetch requests and token refreshing
async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const authStore = useAuthStore();
  const headers = new Headers(options.headers || {});
  
  if (authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`);
  }

  options.headers = headers;
  const response = await fetch(url, options);

  const refreshedToken = response.headers.get('X-Token-Refresh');
  if (refreshedToken) {
    authStore.token = refreshedToken;
    localStorage.setItem('token', refreshedToken);
  }

  return response;
}

interface User {
  id: number;
  username: string;
  is_admin: boolean;
  is_premium?: boolean;
  must_change_password: boolean;
  plan_tier?: string;  // 'free' | 'creator' | 'flagship'
  effective_tier?: string;  // 实际生效档位（Premium 失效回落 free）
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null as string | null,
    user: null as User | null,
    authOptions: null as AuthOptions | null,
    authOptionsLoaded: false,
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    allowRegistration: (state) => state.authOptions?.allow_registration ?? true,
    enableLinuxdoLogin: (state) => state.authOptions?.enable_linuxdo_login ?? false,
    enableWechatLogin: (state) => state.authOptions?.enable_wechat_login ?? false,
    enableGoogleLogin: (state) => state.authOptions?.enable_google_login ?? false,
    enablePhoneLogin: (state) => state.authOptions?.enable_phone_login ?? false,
    captchaEnabled: (state) => state.authOptions?.captcha_enabled ?? false,
    captchaSiteKey: (state) => state.authOptions?.captcha_site_key ?? null,
    mustChangePassword: (state) => state.user?.must_change_password ?? false,
  },
  actions: {
    async fetchAuthOptions(force = false) {
      // 拉取后端认证相关开关，供前端动态渲染
      if (this.authOptionsLoaded && !force) {
        return;
      }
      try {
        const response = await fetch(`${API_URL}/options`);
        if (!response.ok) {
          throw new Error('读取认证开关失败');
        }
        const data = await response.json() as AuthOptions;
        this.authOptions = data;
      } catch (error) {
        console.error('获取认证配置失败，将使用默认值', error);
        this.authOptions = {
          allow_registration: true,
          enable_linuxdo_login: false,
          enable_wechat_login: false,
          enable_google_login: false,
          enable_phone_login: false,
          captcha_enabled: false,
          captcha_site_key: null,
        };
      } finally {
        this.authOptionsLoaded = true;
      }
    },
    async login(username: string, password: string): Promise<boolean> {
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);

      const response = await fetchWithAuth(`${API_URL}/token`, {
        method: 'POST',
        body: params,
      });

      if (!response.ok) {
        throw new Error('Failed to login');
      }

      const data = await response.json();
      this.token = data.access_token;
      if (this.token) {
        localStorage.setItem('token', this.token);
      }
      const mustChangePassword = Boolean(data.must_change_password);
      await this.fetchUser();
      if (this.user) {
        this.user.must_change_password = mustChangePassword || this.user.must_change_password;
      }
      return mustChangePassword;
    },
    async sendPhoneCode(phone: string): Promise<void> {
      const response = await fetch(`${API_URL}/phone/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || '验证码发送失败');
      }
    },
    async phoneLogin(phone: string, code: string): Promise<void> {
      const response = await fetch(`${API_URL}/phone/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, code }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || '手机号登录失败');
      }
      const data = await response.json();
      this.token = data.access_token;
      if (this.token) {
        localStorage.setItem('token', this.token);
      }
      await this.fetchUser();
    },
    // 当前注册流程在 Register.vue 中实现，此处预留方法以兼容旧逻辑
    async register(payload: { username: string; email: string; password: string; verification_code: string }) {
      const response = await fetch(`${API_URL}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail || 'Failed to register';
        throw new Error(detail);
      }
    },
    logout() {
      this.token = null;
      this.user = null;
      localStorage.removeItem('token');
    },
    async fetchUser() {
      if (this.token) {
        try {
          const response = await fetchWithAuth(`${API_URL}/users/me`);

          if (!response.ok) {
            throw new Error('Failed to fetch user');
          }

          const userData = await response.json();
          this.user = {
            id: userData.id,
            username: userData.username,
            is_admin: userData.is_admin || false,
            is_premium: userData.is_premium || false,
            must_change_password: userData.must_change_password || false,
            plan_tier: userData.plan_tier || 'free',
            effective_tier: userData.effective_tier || 'free',
          };
        } catch (error) {
          this.logout();
        }
      }
    },
  },
});
