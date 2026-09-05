import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Vitest 配置：Node 环境运行纯逻辑单测（无需 DOM）。
// 需要 DOM 的组件测试可在用例内通过 // @vitest-environment jsdom 单独切换。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.{test,spec}.ts'],
    globals: true,
  },
})
