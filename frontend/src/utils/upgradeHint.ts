/**
 * 402/403 门控错误 → 升级引导类别判定。
 *
 * 消息来源有三条路径，文案形态不同，但都会带上后端 detail 原文：
 * - http.ts 包装的同步请求错误：`请求失败(402): 积分不足：本次需 40 积分…`（对象上还带 status）
 * - SSE error 事件透传的 detail：`积分不足：…` / `「标准模式」需要创作者版（当前：免费版）`
 * - Go 网关异步任务失败的 error 字符串（与后端 detail 同文案）
 *
 * 传错误对象时优先看 status===402；字符串保留正则路径。
 * 刻意不用裸 `(403)` 匹配——项目归属等无关 403 不应弹升级引导。
 */
import { errorStatus } from './apiError'

export type UpgradeHintKind = 'credits' | 'tier'

const messageOf = (input: unknown): string =>
  typeof input === 'string' ? input : input instanceof Error ? input.message : ''

export const detectUpgradeHint = (input: unknown): UpgradeHintKind | null => {
  const message = messageOf(input)
  if (!message && typeof input !== 'object') return null
  if (typeof input === 'object' && input !== null && errorStatus(input) === 402) return 'credits'
  if (!message) return null
  if (/积分不足|\(402\)/.test(message)) return 'credits'
  if (/需要(创作者|旗舰)|仅(创作者|旗舰)|升级(到|至)?(创作者|旗舰)/.test(message)) return 'tier'
  return null
}
