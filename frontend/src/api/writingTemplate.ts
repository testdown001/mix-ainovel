// 写作模板 API
import { http } from './http'

export interface TemplateParameter {
  name: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'number'
  required: boolean
  description?: string
  options?: string[]
  default?: string
}

export interface WritingTemplate {
  id: number
  name: string
  category: string
  description: string
  icon: string
  prompt_template: string
  parameters: TemplateParameter[]
  use_count: number
  is_builtin: boolean
}

export interface TemplateCategory {
  id: string
  name: string
  icon: string
}

// 获取所有模板
export async function listTemplates(category?: string, search?: string): Promise<WritingTemplate[]> {
  const params = new URLSearchParams()
  if (category) params.append('category', category)
  if (search) params.append('search', search)
  const res = await http.get(`/api/writing-templates?${params}`)
  return res.data
}

// 获取模板分类
export async function getTemplateCategories(): Promise<TemplateCategory[]> {
  const res = await http.get('/api/writing-templates/categories')
  return res.data
}

// 获取单个模板
export async function getTemplate(templateId: number): Promise<WritingTemplate> {
  const res = await http.get(`/api/writing-templates/${templateId}`)
  return res.data
}

// 创建模板
export async function createTemplate(template: Partial<WritingTemplate>): Promise<WritingTemplate> {
  const res = await http.post('/api/writing-templates', template)
  return res.data
}

// 更新模板
export async function updateTemplate(templateId: number, template: Partial<WritingTemplate>): Promise<WritingTemplate> {
  const res = await http.put(`/api/writing-templates/${templateId}`, template)
  return res.data
}

// 删除模板
export async function deleteTemplate(templateId: number): Promise<void> {
  await http.delete(`/api/writing-templates/${templateId}`)
}

// 应用模板
export async function applyTemplate(templateId: number, params: Record<string, any>): Promise<{ prompt: string }> {
  const res = await http.post(`/api/writing-templates/${templateId}/apply`, { params })
  return res.data
}

// AI 推演模板参数
export async function inferTemplateParams(
  templateId: number,
  projectId: string,
  chapterNumber: number
): Promise<Record<string, any>> {
  const res = await http.post(`/api/writing-templates/${templateId}/infer-params`, {
    project_id: projectId,
    chapter_number: chapterNumber,
  })
  return res.data.params
}
