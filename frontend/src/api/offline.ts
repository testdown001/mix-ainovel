// AIMETA P=离线模式处理|R=API_离线降级_测试登录|NR=不含业务逻辑|E=offline|X=internal|A=离线处理器|D=fetch|S=network|RD=./README.ai

/**
 * 离线模式 API 处理器
 * 当后端服务不可用时，提供默认响应、mock 数据和本地登录功能
 */

// 强制离线模式标志 - 开发测试时设为 true
export const FORCE_OFFLINE_MODE = false;

// Mock 用户数据库（仅用于开发测试）
const MOCK_USERS: Record<string, { id: number; username: string; email: string; password: string; is_admin: boolean; must_change_password: boolean }> = {
  'admin': {
    id: 1,
    username: 'admin',
    email: 'admin@arborisnovel.local',
    password: 'admin123',
    is_admin: true,
    must_change_password: false,
  },
  'demo': {
    id: 2,
    username: 'demo',
    email: 'demo@arborisnovel.local',
    password: 'demo123',
    is_admin: false,
    must_change_password: false,
  },
  'writer': {
    id: 3,
    username: 'writer',
    email: 'writer@arborisnovel.local',
    password: 'writer123',
    is_admin: false,
    must_change_password: false,
  },
};

// 存储已登录的用户会话
const MOCK_SESSIONS: Map<string, { userId: number; username: string; email: string; is_admin: boolean }> = new Map();

interface OfflineResponse {
  ok: boolean;
  status: number;
  statusText: string;
  json: () => Promise<any>;
  text: () => Promise<string>;
  headers: Headers;
}

/**
 * 创建离线模式的 Response 对象
 */
function createOfflineResponse(data: any, status: number = 200): OfflineResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Service Unavailable',
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers(),
  };
}

/**
 * 检查后端是否可用
 */
let backendAvailable: boolean | null = null;

export async function isBackendAvailable(): Promise<boolean> {
  // 使用缓存的可用性状态，避免重复检查
  if (backendAvailable !== null) {
    return backendAvailable;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch('/api/health', {
      method: 'HEAD',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    backendAvailable = response.ok;
  } catch (error) {
    console.warn('[Offline Mode] Backend not available:', error);
    backendAvailable = false;
  }

  return backendAvailable;
}

/**
 * 重置后端可用性缓存
 */
export function resetBackendCache() {
  backendAvailable = null;
}

/**
 * 生成 mock token
 */
function generateMockToken(userId: number, username: string): string {
  return `mock_token_${userId}_${username}_${Date.now()}`;
}

/**
 * 解析 FormData 或 URLSearchParams
 */
function parseFormData(body: any): Record<string, string> {
  if (body instanceof URLSearchParams) {
    const obj: Record<string, string> = {};
    body.forEach((value, key) => {
      obj[key] = value;
    });
    return obj;
  }
  return {};
}

/**
 * 拦截 fetch 请求，在后端不可用时返回离线响应
 */
export async function fetchWithOfflineSupport(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  // 只在 /api 路由上应用离线支持
  if (!url.includes('/api')) {
    return fetch(url, options);
  }

  const available = await isBackendAvailable();
  const shouldUseOffline = FORCE_OFFLINE_MODE || !available;

  // 处理登录请求 - 优先级最高
  if (url.includes('/auth/token') && options.method === 'POST') {
    if (shouldUseOffline) {
      console.log('[Offline Mode] Processing login request');
      const formData = parseFormData(options.body);
      const username = formData.username || '';
      const password = formData.password || '';

      // 检查用户和密码
      const user = MOCK_USERS[username];
      if (user && user.password === password) {
        const token = generateMockToken(user.id, user.username);
        MOCK_SESSIONS.set(token, {
          userId: user.id,
          username: user.username,
          email: user.email,
          is_admin: user.is_admin,
        });
        console.log(`[Offline Mode] Login successful for user: ${username}`);
        return createOfflineResponse({
          access_token: token,
          token_type: 'bearer',
          must_change_password: false,
        });
      } else {
        console.warn(`[Offline Mode] Login failed for user: ${username}`);
        return createOfflineResponse(
          { detail: 'Invalid credentials' },
          401
        );
      }
    }
  }

  // 处理获取当前用户信息
  if (url.includes('/users/me')) {
    if (shouldUseOffline) {
      // 从 Authorization header 中提取 token
      const headers = new Headers(options.headers);
      const authHeader = headers.get('Authorization');
      const token = authHeader?.replace('Bearer ', '');

      if (token && MOCK_SESSIONS.has(token)) {
        const session = MOCK_SESSIONS.get(token)!;
        console.log(`[Offline Mode] Returning user info for: ${session.username}`);
        return createOfflineResponse({
          id: session.userId,
          username: session.username,
          email: session.email,
          is_admin: session.is_admin,
          must_change_password: false,
        });
      }
    }
  }

  if (!shouldUseOffline && available) {
    return fetch(url, options);
  }

  // 后端不可用或强制离线模式，返回离线响应
  console.log(`[Offline Mode] Using offline response for ${url}`);

  // 根据不同的 API 路由返回合适的离线数据
  if (url.includes('/auth/options')) {
    return createOfflineResponse({
      allow_registration: true,
      enable_linuxdo_login: false,
    });
  }

  // 其他 API 请求返回通用错误
  return createOfflineResponse(
    { detail: '服务暂时不可用，请稍后重试' },
    503
  );
}

/**
 * 离线模式指示器
 * 返回当前是否处于离线模式
 */
export async function isOfflineMode(): Promise<boolean> {
  return !(await isBackendAvailable());
}
