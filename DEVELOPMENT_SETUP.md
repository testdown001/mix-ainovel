# 开发环境设置指南

## 问题说明

当前项目包含前端（Vue.js）和后端（FastAPI）两个部分。在 v0 开发环境中，后端服务可能无法运行，导致以下错误：

```
[vite] http proxy error: /api/auth/options
Error: connect ECONNREFUSED 127.0.0.1:8000
```

## 解决方案

### 1. 离线开发模式（推荐）

前端已配置为离线模式，当后端服务不可用时：
- Vite 代理配置已被注释
- API 请求会包含 5-10 秒的超时机制
- 认证模块会使用默认配置
- 用户认证会显示连接错误提示

### 2. 使用本地后端

如果要运行完整的前后端集成，需要：

#### 安装依赖
```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 启动后端服务
```bash
# 在激活的虚拟环境中
uvicorn app.main:app --reload --port 8000
```

#### 启用 Vite 代理

编辑 `frontend/vite.config.ts`，取消注释以下部分：

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
      timeout: 1800000,
    }
  }
}
```

#### 启动前端开发服务器
```bash
cd frontend
npm install
npm run dev
```

### 3. 环境变量

前端环境变量位于 `frontend/.env.development`：

```env
VITE_API_TIMEOUT=10000        # API 请求超时时间（毫秒）
VITE_OFFLINE_MODE=true         # 离线模式标志
```

## 故障排除

### 仍然出现连接错误

1. 检查 `vite.config.ts` 中的代理配置是否被正确注释
2. 检查浏览器控制台是否有其他错误信息
3. 尝试清除缓存：`npm run dev` 前删除 `node_modules/.vite`

### 需要完整后端功能

后端服务必须运行在 `http://127.0.0.1:8000`。启动后：
1. 取消 `vite.config.ts` 中的代理配置注释
2. 重启前端开发服务器
3. 刷新浏览器

## 架构说明

- **前端**：Vue 3 + Pinia（状态管理）+ Vite
- **后端**：FastAPI + SQLAlchemy + PostgreSQL
- **通信**：RESTful API
- **认证**：JWT Token

前端已实现优雅降级机制，可在后端不可用时继续开发 UI 和交互逻辑。
