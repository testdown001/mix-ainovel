import { defineConfig, devices } from '@playwright/test'

// E2E 冒烟：uvicorn 同源托管 API + 前端 dist（先 npm run build-only 产出 dist）。
// 全部路径零 LLM 依赖，守住「登录/建项目/页面渲染」这些基础链路不被样式或路由改动打断。
const PORT = Number(process.env.E2E_PORT || 8130)
const BASE_URL = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list']] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'bash e2e/start-backend.sh',
    url: `${BASE_URL}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
