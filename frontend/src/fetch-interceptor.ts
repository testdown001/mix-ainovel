/**
 * 全局 Fetch 拦截器
 * 在应用启动时激活，拦截所有 /api 请求
 * 当后端不可用时自动使用离线模式
 */

import { fetchWithOfflineSupport } from '@/api/offline';

// 保存原始 fetch
const originalFetch = window.fetch;

// 全局拦截 fetch
window.fetch = ((url: string | Request, options?: RequestInit) => {
  // 将 Request 对象转换为字符串 URL
  const urlString = typeof url === 'string' ? url : url.url;

  console.log('[v0] Intercepting fetch:', urlString);

  // 所有 /api 请求都通过离线支持处理
  if (urlString.includes('/api')) {
    return fetchWithOfflineSupport(urlString, options);
  }

  // 其他请求直接使用原始 fetch
  return originalFetch(url as RequestInfo | URL, options);
}) as typeof fetch;
