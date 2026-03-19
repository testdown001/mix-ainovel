# 离线模式开发指南

本指南说明如何在没有后端服务的情况下，在本地开发环境中体验完整的 UI 和功能。

## 快速开始

### 1. 启动前端开发服务器

```bash
cd frontend
npm install
npm run dev
```

前端服务将在 `http://localhost:5173` 运行。

## 离线登录

当后端服务 (`http://127.0.0.1:8000`) 不可用时，应用会自动进入**离线模式**，使用本地 mock 认证系统。

### 测试账号

以下账号可以在离线模式下使用：

| 用户名 | 密码 | 角色 | 用途 |
|--------|------|------|------|
| `admin` | `admin123` | 管理员 | 查看管理员功能和设置 |
| `demo` | `demo123` | 普通用户 | 查看核心创作功能 |
| `writer` | `writer123` | 普通用户 | 另一个普通用户账号 |

### 登录步骤

1. 打开 `http://localhost:5173/login`
2. 输入任意测试账号的用户名和密码（见上表）
3. 点击"登录"按钮
4. 应该会重定向到首页，离线模式自动工作

## 离线模式工作原理

- **自动激活**：当后端连接失败时，应用自动进入离线模式
- **Mock 认证**：所有登录请求由前端本地处理，无需后端
- **Session 存储**：登录令牌存储在内存中（刷新页面会失效）
- **模拟数据**：各 API 端点返回预定义的响应结构

## 功能限制

在离线模式下，以下功能受限：

- ❌ 数据持久化（刷新页面后数据会丢失）
- ❌ 实时 WebSocket 通信（Agent 长任务功能）
- ❌ 与后端 AI 模型的交互（所有 AI 功能）
- ❌ 数据库操作（增删改查小说、章节等）

## 完整功能

若要体验完整功能，需要启动后端服务：

```bash
# 在另一个终端中
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端启动后，应用会自动检测到并切换到在线模式。

## 强制离线模式

如果需要强制使用离线模式（即使后端已启动），可以修改 `frontend/src/api/offline.ts`：

```typescript
// 强制离线模式标志 - 开发测试时设为 true
export const FORCE_OFFLINE_MODE = true;
```

设置后需要重新启动开发服务器。

## 调试

可以在浏览器控制台查看离线模式日志：

```javascript
// 查看离线模式状态
console.log('[Offline Mode] ...')
```

## 下一步

1. 浏览 UI 和各个功能模块
2. 了解项目架构和组件设计
3. 准备好后端后，切换到完整模式进行集成测试
