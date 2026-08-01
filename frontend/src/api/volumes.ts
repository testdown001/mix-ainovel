/**
 * 分卷规划 / 卷级复盘 / 卷级发散卡片
 *
 * 后端把「复盘自动重规划」与「作者主动发散」写进同一个 replan 槽位，
 * 因此前端也用同一份数据结构展示，靠 replan.source 区分来源。
 */
import { requestJson } from './http'

export interface VolumeRetrospective {
  achieved?: string
  drift?: string
  unresolved?: string[]
  source_chapter?: number
}

export interface VolumeReplan {
  arc_goal?: string
  climax_hint?: string
  focus?: string
  avoid?: string
  /** 'divergence' = 作者选的发散卡片；缺省 = 卷级复盘自动产出 */
  source?: string
  title?: string
  status?: string
}

export interface VolumePlan {
  name?: string
  start_chapter?: number
  end_chapter?: number
  arc_goal?: string
  climax_hint?: string
  retrospective?: VolumeRetrospective
  replan?: VolumeReplan
}

export interface VolumeDivergenceCard {
  title: string
  arc_goal: string
  climax_hint: string
  focus: string
  avoid: string
  hook: string
  surprise?: number
  continuity?: number
  tension?: number
  score?: number
  comment?: string
}

const BASE = '/api/novels'

export const VolumesAPI = {
  list: (projectId: string) =>
    requestJson<{ volumes: VolumePlan[]; tier: string; can_diverge: boolean }>(
      `${BASE}/${projectId}/volumes`,
    ),

  /** N 路发散（旗舰档，约 2 次 LLM 调用，耗时较久） */
  diverge: (projectId: string, volumeNumber: number, payload: { n?: number; keep?: number } = {}) =>
    requestJson<{ cards: VolumeDivergenceCard[]; tier: string }>(
      `${BASE}/${projectId}/volumes/${volumeNumber}/diverge`,
      { method: 'POST', body: JSON.stringify({ n: payload.n ?? 5, keep: payload.keep ?? 3 }) },
    ),

  /** 应用选中的卡片：写入该卷 replan，即刻对后续章节生成生效 */
  apply: (
    projectId: string,
    volumeNumber: number,
    card: Pick<VolumeDivergenceCard, 'title' | 'arc_goal' | 'climax_hint' | 'focus' | 'avoid'>,
  ) =>
    requestJson<{ applied: boolean; volume_number: number }>(
      `${BASE}/${projectId}/volumes/${volumeNumber}/diverge/apply`,
      { method: 'POST', body: JSON.stringify(card) },
    ),
}
