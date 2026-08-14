// E2E 冒烟：6 条零 LLM 依赖的核心链路。被测服务由 playwright.config.ts 的
// webServer 拉起（uvicorn 同源托管 API + dist），普通用户由 seed_e2e_user.py 播种。
import { test, expect, request as pwRequest, type Page } from '@playwright/test'

const E2E_USERNAME = 'e2euser'
const E2E_PASSWORD = 'e2e-password-123'

async function apiToken(baseURL: string): Promise<string> {
  const ctx = await pwRequest.newContext({ baseURL })
  const res = await ctx.post('/api/auth/token', {
    form: { username: E2E_USERNAME, password: E2E_PASSWORD },
  })
  expect(res.ok(), `登录接口失败: ${res.status()}`).toBeTruthy()
  const data = await res.json()
  await ctx.dispose()
  return data.access_token as string
}

/** 注入 token 直达已登录态（auth store 启动时读 localStorage.token） */
async function injectAuth(page: Page, token: string): Promise<void> {
  await page.addInitScript((value: string) => {
    window.localStorage.setItem('token', value)
  }, token)
}

test('落地页渲染：标题与 CTA 可见', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toContainText('都有百万字长篇')
  // 落地页 hero 与定价区各有一个同名 CTA，取首个（hero 区）
  await expect(page.getByRole('button', { name: '免费开始创作' }).first()).toBeVisible()
})

test('普通用户登录 → 跳转 /home 工作台入口', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(E2E_USERNAME)
  await page.getByPlaceholder('请输入密码').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('**/home')
  await expect(page.getByText('我的小说库')).toBeVisible()
})

test('新建项目（API）→ 写作台壳渲染', async ({ page, baseURL }) => {
  const token = await apiToken(baseURL!)
  const ctx = await pwRequest.newContext({
    baseURL: baseURL!,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  })
  const res = await ctx.post('/api/novels', {
    data: { title: 'E2E冒烟项目', initial_prompt: 'E2E 冒烟测试用项目' },
  })
  expect(res.status(), `创建项目失败: ${await res.text()}`).toBe(201)
  const project = await res.json()
  await ctx.dispose()

  await injectAuth(page, token)
  await page.goto(`/novel/${project.id}`)
  // 无蓝图不重定向，壳（头部含项目标题）应正常渲染
  await expect(page.getByText('E2E冒烟项目').first()).toBeVisible({ timeout: 15_000 })
  expect(page.url()).toContain(`/novel/${project.id}`)
})

test('设置页标签切换：写作偏好 / 积分明细 / 邀请返积分', async ({ page, baseURL }) => {
  const token = await apiToken(baseURL!)
  await injectAuth(page, token)
  await page.goto('/settings')

  // 默认标签：写作偏好
  await expect(page.getByText('写作风格偏好')).toBeVisible()

  await page.getByRole('button', { name: '积分明细' }).click()
  await expect(page.getByRole('button', { name: '积分明细' })).toBeVisible()

  await page.getByRole('button', { name: '邀请返积分' }).click()
  // ReferralPanel 加载完成（quota/referral 接口自动建行，无外部依赖）
  await expect(page.getByText('我的邀请链接')).toBeVisible({ timeout: 10_000 })
})

test('定价页（公开）渲染', async ({ page }) => {
  await page.goto('/pricing')
  await expect(page.locator('h1')).toContainText('选择你的创作套餐')
})

test('无效分享链接：提示已失效而非白屏/JSON', async ({ page }) => {
  await page.goto('/share/invalid-token-for-e2e')
  await expect(page.getByText('链接已失效')).toBeVisible({ timeout: 10_000 })
})
