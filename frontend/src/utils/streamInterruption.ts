/**
 * 生成流「连接中断」与「生成失败」的区分。
 *
 * 这两件事对用户的含义完全相反，此前却共用一句「生成章节失败」：
 * - 业务失败（402 积分不足 / 403 档位不足 / 502 正文校验未过）：重试没用，要么换档要么改内容。
 * - 连接中断（网络抖动、切页面、代理超时）：服务端多半还在写。2026-08-14 线上实测
 *   （nginx → uvicorn，掐断 curl）：生成一路跑到落库 + 异步收尾，章节最终是
 *   waiting_for_confirm——断线丢的只是这条推送，不是这一章。
 *
 * 所以判定出中断后不能自行猜结论，必须回头问后端真实状态（见 WritingDesk 的
 * reconcileInterruptedChapter）：已落库就把成果交出来，仍在生成就说清楚并让轮询接管。
 * 一句含糊的「生成失败」会让用户以为积分白花，于是刷新 + 再点一次生成——那才是真的
 * 白烧一次上游调用。
 */

/** 流已结束但没收到 completed 事件时抛出的错误（见 api/novel.ts）。 */
export class StreamInterruptedError extends Error {
  readonly interrupted = true

  constructor(message = '生成连接中断') {
    super(message)
    this.name = 'StreamInterruptedError'
  }
}

/** 浏览器在网络层中断 fetch 流时给出的错误特征（各内核文案不同，故按关键词匹配）。 */
const NETWORK_INTERRUPTION_PATTERNS = [
  'network error',
  'networkerror', // Firefox: "NetworkError when attempting to fetch resource."
  'failed to fetch',
  'load failed',
  'network connection was lost',
  'connection closed',
  'err_network',
  'err_connection',
  'aborted',
  'the operation was aborted',
]

export function isStreamInterruption(error: unknown): boolean {
  if (error instanceof StreamInterruptedError) {
    return true
  }
  if (typeof error === 'object' && error !== null && (error as { interrupted?: boolean }).interrupted) {
    return true
  }
  const message = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  if (!message) {
    return false
  }
  const normalized = message.toLowerCase()
  // 带 HTTP 状态码的一律是业务错误：服务端答复过了，不是连接问题
  if (/\((4\d\d|5\d\d)\)/.test(normalized) || /状态码/.test(message)) {
    return false
  }
  return NETWORK_INTERRUPTION_PATTERNS.some((pattern) => normalized.includes(pattern))
}
