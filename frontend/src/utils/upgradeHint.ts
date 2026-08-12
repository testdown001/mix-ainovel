/**
 * 402/403 门控错误 → 升级引导类别判定。
 *
 * 消息来源有三条路径，文案形态不同，但都会带上后端 detail 原文：
 * - http.ts 包装的同步请求错误：`请求失败(402): 积分不足：本次需 40 积分…`
 * - SSE error 事件透传的 detail：`积分不足：…` / `「标准模式」需要创作者版（当前：免费版）`
 * - Go 网关异步任务失败的 error 字符串（与后端 detail 同文案）
 *
 * 刻意不用裸 `(403)` 匹配——项目归属等无关 403 不应弹升级引导。
 */
export type UpgradeHintKind = 'credits' | 'tier'

export const detectUpgradeHint = (message: string): UpgradeHintKind | null => {
  if (!message) return null
  if (/积分不足|\(402\)/.test(message)) return 'credits'
  if (/需要(创作者|旗舰)|仅(创作者|旗舰)|升级(到|至)?(创作者|旗舰)/.test(message)) return 'tier'
  return null
}
