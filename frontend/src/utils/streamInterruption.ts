/**
 * 生成流「连接中断」与「生成失败」的区分。
 *
 * 这两件事对用户的含义完全相反，此前却共用一句「生成章节失败」：
 * - 业务失败（402 积分不足 / 403 档位不足 / 502 正文校验未过）：重试没用，要么换档要么改内容。
 * - 连接中断（网络抖动、切页面、代理超时）：后端的生产者任务会被一并取消、积分已退回，
 *   章节回落 failed，**重新点一次生成就行**。
 *
 * 报成「失败」的代价是真实的：用户以为白扣了积分，先刷新再重点一次，我们这边多一次
 * 上游调用。所以中断必须能被识别出来，并给出与后端真实状态一致的说法。
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
