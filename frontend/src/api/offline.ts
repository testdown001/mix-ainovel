// AIMETA P=离线模式处理|R=API_离线降级|NR=不含业务逻辑|E=offline|X=internal|A=离线处理器|D=fetch|S=network|RD=./README.ai

/**
 * 离线模式 API 处理器
 * 当后端服务不可用时，提供默认响应或缓存数据
 */

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

  if (available) {
    return fetch(url, options);
  }

  // 后端不可用，返回离线响应
  console.warn(`[Offline Mode] Using offline response for ${url}`);

  // 根据不同的 API 路由返回合适的离线数据
  if (url.includes('/auth/options')) {
    return createOfflineResponse({
      allow_registration: true,
      enable_linuxdo_login: false,
    });
  }

  if (url.includes('/auth/token')) {
    // 登录请求失败
    return createOfflineResponse(
      { detail: '无法连接到服务器' },
      503
    );
  }

  if (url.includes('/users/me')) {
    // 获取用户信息失败
    return createOfflineResponse(
      { detail: '无法连接到服务器' },
      503
    );
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
