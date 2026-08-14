/**
 * 生成路径错误文案用户化：把后端/网关的原始错误转成用户语言。
 *
 * 定位在既有两层判定**之后**的最后一环（调用方职责，不在这里重复判定）：
 * - 402/403 门控 → upgradeHint.ts 的升级引导，不进这里
 * - 连接中断 → streamInterruption.ts 的对账流程，不进这里
 * 剩下的才是「真的失败了、要向用户解释」的错误：正文校验 502、上游超时 500、
 * 搜索通道未配置 503、网关限流 429，以及兜底。
 *
 * 刻意不做自动重试：生成是计费操作，52x 自动重跑会产生真实的重复上游调用——
 * 后端对失败任务已有退款补偿（refund_generation / _mark_chapter_interrupted_safely），
 * 文案告诉用户「积分已退回、可以再点一次」即可，重试的决定权留给用户。
 */

export interface HumanizedError {
  title: string
  message: string
  /** 建议动作（retry=可直接重试 / wait=稍候再试 / contact_admin=需要管理员介入） */
  action?: 'retry' | 'wait' | 'contact_admin'
}

export interface HumanizeOptions {
  /**
   * 本次操作是否计费。章节生成先扣后跑、失败退款，文案要讲清「积分已退回」；
   * 蓝图生成不计费（blueprint:generate 无积分账单），提退款反而制造困惑。
   */
  billed?: boolean
}

/** 消息形态（与 upgradeHint 同源）：http.ts 包装的 `请求失败(502): …`、SSE/任务透传的后端 detail 原文。 */
export function humanizeGenerationError(
  raw: string,
  options: HumanizeOptions = {},
): HumanizedError {
  const billed = options.billed !== false
  const message = raw || '未知错误'

  // 正文校验未通过（后端已做过一次低温硬约束重试仍失败才 502）
  if (/正文校验未通过|\(502\)/.test(message)) {
    return {
      title: 'AI 产出未达标',
      message: billed
        ? 'AI 这次的产出不合格，已自动重试仍未通过。积分已退回，直接再点一次生成即可。'
        : 'AI 这次的产出不合格，已自动重试仍未通过。直接再点一次生成即可。',
      action: 'retry',
    }
  }

  // 搜索通道未配置（后端 503 detail：「未配置参考小说搜索模型（llm_search.*）…」）
  if (/未配置(参考小说)?搜索|搜索(模型|通道)?(与.*)?均?未配置/.test(message)) {
    return {
      title: '联网搜索不可用',
      message: '管理员尚未配置联网搜索模型，联网找料暂时不可用，其余功能不受影响。',
      action: 'contact_admin',
    }
  }

  // 服务端 500 / 上游超时
  if (/\(500\)|状态码: 500|超时|timeout|timed out/i.test(message)) {
    return {
      title: '服务端处理超时',
      message: billed
        ? '服务端处理超时，积分已退回，请稍后重试。'
        : '服务端处理超时，请稍后重试。',
      action: 'retry',
    }
  }

  // 网关/后端限流（网关任务并发上限的定制文案不在此列，走兜底保留原文）
  if (/\(429\)|限流|太频繁|操作过于频繁|too many requests|rate ?limit/i.test(message)) {
    return {
      title: '操作太频繁',
      message: '操作太频繁，稍等几秒再试。',
      action: 'wait',
    }
  }

  // 兜底：保留原文（后端 detail 常常已是可读中文），补一句求助出口
  return {
    title: '生成失败',
    message: `${message}（如反复出现请联系管理员）`,
    action: 'contact_admin',
  }
}
