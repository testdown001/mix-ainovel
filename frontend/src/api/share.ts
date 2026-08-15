// AIMETA P=作品公开分享API客户端|R=公开只读端点_owner分享开关|E=shareApi|X=internal|A=api对象|D=fetch|S=net
import { requestJson } from './http'

export interface SharedChapterMeta {
  chapter_number: number
  title: string
  word_count: number
}

export interface SharedNovelOverview {
  title: string
  description: string | null
  author_name: string
  chapter_count: number
  chapters: SharedChapterMeta[]
  author_invite_code: string
  ai_assisted?: boolean
}

export interface SharedChapterContent {
  chapter_number: number
  title: string
  content: string
  prev: number | null
  next: number | null
  ai_assisted?: boolean
}

export interface ShareStatus {
  enabled: boolean
  share_token: string | null
}

/** 链接无效/已关闭分享：阅读页据此渲染「链接已失效」而非通用报错。 */
export class ShareNotFoundError extends Error {
  constructor() {
    super('分享链接不存在或已失效')
    this.name = 'ShareNotFoundError'
  }
}

// 公开端点免登录：不走 requestJson——它会自动附带 Authorization，
// 且对 401 做登出跳转，这些行为都不该出现在游客阅读页上
const publicJson = async <T>(url: string): Promise<T> => {
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  if (response.status === 404) throw new ShareNotFoundError()
  if (!response.ok) throw new Error(`请求失败，状态码: ${response.status}`)
  return response.json() as Promise<T>
}

export const shareApi = {
  /** 公开：分享目录（作品元信息 + 已完稿章节列表）。 */
  getSharedNovel: (token: string) =>
    publicJson<SharedNovelOverview>(`/api/public/shared/${encodeURIComponent(token)}`),

  /** 公开：章节正文 + 相邻已完稿章号。 */
  getSharedChapter: (token: string, chapterNumber: number) =>
    publicJson<SharedChapterContent>(
      `/api/public/shared/${encodeURIComponent(token)}/chapters/${chapterNumber}`
    ),

  /** owner：当前分享状态。 */
  getStatus: (projectId: string) => requestJson<ShareStatus>(`/api/novels/${projectId}/share`),

  /** owner：开启分享（幂等，已开启返回现有 token）。 */
  enable: (projectId: string) =>
    requestJson<{ share_token: string; share_url_path: string }>(
      `/api/novels/${projectId}/share`,
      { method: 'POST' }
    ),

  /** owner：关闭分享（旧链接立刻失效）。 */
  disable: (projectId: string) =>
    requestJson<void>(`/api/novels/${projectId}/share`, { method: 'DELETE' }),
}
