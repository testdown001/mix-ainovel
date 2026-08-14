import { describe, expect, it } from 'vitest'
import { useGenerationProgress } from './useGenerationProgress'

describe('useGenerationProgress（三种来源共用的进度状态机）', () => {
  it('未开始时忽略阶段事件（上一次生成的迟到事件不该点亮进度）', () => {
    const p = useGenerationProgress()
    p.applyStage({ stage: 'generate_versions' })
    expect(p.percent.value).toBe(0)
    expect(p.logs.value).toHaveLength(0)
    expect(p.label.value).toBe('')
  })

  it('按阶段推进，并累积可读日志', () => {
    const p = useGenerationProgress()
    p.start(3, 'stream')
    p.applyStage({ stage: 'starting', message: '开始生成章节' })
    p.applyStage({ stage: 'generate_versions', message: '多版本生成中' })
    p.applyStage({ stage: 'post_consistency', message: '一致性校对' })

    expect(p.label.value).toBe('一致性校对')
    expect(p.percent.value).toBe(62)
    expect(p.logs.value.map((l) => l.label)).toEqual([
      '准备生成',
      '撰写正文（多版本）',
      '一致性校对',
    ])
  })

  it('进度单调不回退——后处理链有并行与跳过，事件顺序不保证递增', () => {
    const p = useGenerationProgress()
    p.start(1, 'async')
    p.applyStage({ stage: 'post_six_dimension' }) // 84
    p.applyStage({ stage: 'post_consistency' }) // 62，迟到事件
    expect(p.percent.value).toBe(84)
  })

  it('来源自带的百分比与本地映射取较大值（网关任务状态里有自己的进度）', () => {
    const p = useGenerationProgress()
    p.start(1, 'async')
    p.applyStage({ stage: 'generate_versions', percent: 70 })
    expect(p.percent.value).toBe(70)
  })

  it('重复阶段不重复记日志', () => {
    const p = useGenerationProgress()
    p.start(1, 'stream')
    p.applyStage({ stage: 'post_polish' })
    p.applyStage({ stage: 'post_polish' })
    expect(p.logs.value.filter((l) => l.label === '润色')).toHaveLength(1)
  })

  it('降级显式记录且同一原因只说一次', () => {
    const p = useGenerationProgress()
    p.start(1, 'async')
    p.markDegraded('实时进度推送已断开，已改为轮询获取进度')
    p.markDegraded('实时进度推送已断开，已改为轮询获取进度')
    expect(p.degraded.value).toBe(true)
    expect(p.logs.value.filter((l) => l.label.includes('轮询'))).toHaveLength(1)
  })

  it('来源标签用用户语言，不暴露 async/stream', () => {
    const p = useGenerationProgress()
    p.start(1, 'async')
    expect(p.sourceLabel.value).toBe('后台任务')
    p.start(1, 'stream')
    expect(p.sourceLabel.value).toBe('直连生成')
  })

  it('重新开始会清空上一章的痕迹', () => {
    const p = useGenerationProgress()
    p.start(1, 'stream')
    p.applyStage({ stage: 'post_six_dimension' })
    p.markDegraded('降级了')
    p.start(2, 'async')

    expect(p.chapterNumber.value).toBe(2)
    expect(p.percent.value).toBe(2)
    expect(p.logs.value.map((l) => l.label)).toEqual(['准备生成'])
    expect(p.degraded.value).toBe(false)
  })

  it('finish 收到 100 并停用', () => {
    const p = useGenerationProgress()
    p.start(1, 'stream')
    p.finish()
    expect(p.percent.value).toBe(100)
    expect(p.active.value).toBe(false)
  })
})
