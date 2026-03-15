# Arboris-Novel 部署与运行指南

## 目录

- [系统要求](#系统要求)
- [架构总览](#架构总览)
- [方式一：Docker 一键部署（推荐）](#方式一docker-一键部署推荐)
- [方式二：本地开发环境](#方式二本地开发环境)
- [方式三：生产环境集群部署](#方式三生产环境集群部署)
- [环境变量说明](#环境变量说明)
- [Go Gateway 配置](#go-gateway-配置)
- [数据库管理](#数据库管理)
- [日志与监控](#日志与监控)
- [常见问题](#常见问题)

---

## 系统要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端运行时 |
| Node.js | ^20.19.0 或 >=22.12.0 | 前端构建 |
| MySQL | 8.0+ | 主数据库 |
| Redis | 7.0+ | 缓存 / 消息队列 / Celery Broker |
| Go | 1.22+ | Go Gateway 编译（可选） |
| Docker | 20.10+ | 容器化部署 |
| Docker Compose | v2+ | 编排服务 |

---

## 架构总览

```
                        +-----------------+
                        |    Nginx (LB)   | :80/:443
                        +--------+--------+
                                 |
              +------------------+------------------+
              |                                     |
     +--------v--------+                   +--------v--------+
     |  Go API Gateway  | :3000            |  Go API Gateway  | :3000
     |  (JWT/限流/WS)   |                  |  (JWT/限流/WS)   |
     +--------+---------+                  +--------+---------+
              |                                     |
     +--------v-----------------------------------------v--------+
     |                    FastAPI (Python)                         | :8000
     |            (业务逻辑 / LLM 调用 / RAG)                      |
     +-------+-------------------+-------------------+------------+
             |                   |                   |
     +-------v------+   +-------v------+   +---------v--------+
     |    MySQL     |   |    Redis     |   |     Qdrant       |
     |   :3306      |   |   :6379      |   |    :6333         |
     +-------+------+   +-------+------+   +------------------+
```

**两种运行模式：**
- **简单模式**（无 Go Gateway）：Nginx -> FastAPI，使用 SSE 流式生成
- **完整模式**（含 Go Gateway）：Nginx -> Go Gateway -> FastAPI，使用 WebSocket + 异步任务队列

---

## 方式一：Docker 一键部署（推荐）

适合快速体验和小规模单机部署。前端和后端打包在同一个 Docker 镜像中，由 Supervisor 管理 Nginx + Uvicorn。

### 1. 前置准备

确保已安装 Docker 和 Docker Compose，并且有一个可用的 MySQL 数据库。

### 2. 配置环境变量

```bash
cd deploy
cp .env.example .env
```

编辑 `.env`，**必须修改的项**：

```env
# 加密密钥（生成方式：openssl rand -hex 32）
SECRET_KEY=你的随机密钥

# MySQL 连接（使用宿主机数据库时 host 填 host.docker.internal）
MYSQL_HOST=host.docker.internal
MYSQL_PORT=3306
MYSQL_USER=arboris
MYSQL_PASSWORD=你的数据库密码
MYSQL_DATABASE=arboris

# LLM API（必须配置，否则无法生成章节）
OPENAI_API_KEY=sk-your-api-key
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini

# 管理员账户（首次启动自动创建）
ADMIN_DEFAULT_PASSWORD=设置一个强密码
```

### 3. 创建数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS arboris DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'arboris'@'%' IDENTIFIED BY '你的数据库密码';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON arboris.* TO 'arboris'@'%'; FLUSH PRIVILEGES;"
```

> 表结构会在应用首次启动时由 `init_db()` 自动创建，无需手动建表。

### 4. 构建并启动

```bash
cd deploy
docker compose up -d
```

### 5. 验证

```bash
# 健康检查
curl http://localhost:8088/api/health

# 查看日志
docker compose logs -f app
```

访问 `http://localhost:8088` 即可使用。默认端口由 `.env` 中的 `APP_PORT` 控制。

---

## 方式二：本地开发环境

适合二次开发和调试。

### 1. 启动外部依赖

```bash
# Redis（必需）
docker run -d --name arboris-redis -p 6379:6379 redis:7-alpine

# MySQL（如果本地没有的话）
docker run -d --name arboris-mysql -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=123456 \
  -e MYSQL_DATABASE=arboris \
  mysql:8.0 --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
```

### 2. 后端

```bash
cd backend

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp env.example .env
# 编辑 .env，填入 MySQL 连接信息、OPENAI_API_KEY 等

# 启动（支持热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后可访问：
- API：`http://localhost:8000`
- Swagger 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`

### 3. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（自动代理 /api 到 localhost:8000）
npm run dev
```

前端开发服务器默认在 `http://localhost:5173`。Vite 会自动将 `/api` 请求代理到后端（超时 30 分钟，适配 LLM 长请求）。

### 4. Go Gateway（可选）

如需使用 WebSocket 实时推送和异步任务功能：

```bash
cd gateway

# 编辑配置
# 确认 config.yaml 中 backend.fastapi_url 指向 http://localhost:8000
# 确认 jwt.secret 与后端 .env 中的 SECRET_KEY 一致

# 启动
go run cmd/gateway/main.go
```

Gateway 默认在 `:3000`。前端会自动检测 Gateway 是否可用，不可用时回退到 SSE 模式。

### 5. 快捷脚本（tmux）

后端提供了开发环境一键启动脚本，会自动启动 FastAPI + Celery Worker + Flower：

```bash
cd backend

# 启动（需要 tmux）
bash start-dev.sh

# 停止
bash stop-dev.sh
```

启动后的 tmux 窗口：
- 窗口 0：FastAPI（`http://localhost:8000`）
- 窗口 1：Celery Worker（4 并发）
- 窗口 2：Flower 监控（`http://localhost:5555`）

管理命令：`tmux attach -t arboris`，`Ctrl+B` + 数字键切换窗口。

---

## 方式三：生产环境集群部署

适合多用户并发场景，支持水平扩展。

### 1. 配置环境变量

```bash
cd deploy
cp .env.example .env
```

额外需要配置：

```env
# MySQL root 密码（docker-compose.prod.yml 会自动创建 MySQL 容器）
MYSQL_ROOT_PASSWORD=一个强密码

# Redis URL
REDIS_URL=redis://redis:6379/0
```

### 2. 构建并启动

```bash
cd deploy
docker compose -f docker-compose.prod.yml up -d
```

### 3. 服务清单

| 服务 | 副本数 | 端口 | 说明 |
|------|--------|------|------|
| nginx | 1 | 80, 443 | 负载均衡入口 |
| gateway | 2 | 3000 | Go API Gateway（JWT/限流/WebSocket） |
| app | 3 | 8000 | FastAPI 业务实例 |
| celery-worker-chapter | 3 | - | Celery 章节生成 Worker（4 并发/实例） |
| celery-worker-batch | 2 | - | Celery 批量生成 Worker（2 并发/实例） |
| celery-beat | 1 | - | 定时任务调度器 |
| flower | 1 | 5555 | Celery 监控面板 |
| mysql | 1 | 3306 | MySQL 8.0 数据库 |
| redis | 1 | 6379 | Redis 7 缓存/消息队列 |
| qdrant | 1 | 6333 | 向量数据库（Mem0 长期记忆） |

### 4. Nginx 路由规则

生产环境 Nginx 的请求分发逻辑：

| 路径 | 目标 | 说明 |
|------|------|------|
| `/ws` | Go Gateway | WebSocket 连接 |
| `/tasks/` | Go Gateway | 异步任务 API |
| `/llm/` | Go Gateway | LLM Gateway |
| `/metrics` | Go Gateway | Prometheus 指标 |
| `/api/` | Go Gateway | 业务 API（经 JWT 认证 + 限流） |
| `/health` | Go Gateway | 健康检查 |
| 其他 | FastAPI | 静态资源 |

### 5. SSL 配置

将证书文件放到 `deploy/ssl/` 目录，然后在 `deploy/nginx.conf` 中取消 HTTPS 相关注释。

### 6. 扩缩容

```bash
# 增加 FastAPI 实例到 5 个
docker compose -f docker-compose.prod.yml up -d --scale app=5

# 增加 Celery Worker
docker compose -f docker-compose.prod.yml up -d --scale celery-worker-chapter=5
```

---

## 环境变量说明

### 核心（必需）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | - | JWT 加密密钥，`openssl rand -hex 32` 生成 |
| `OPENAI_API_KEY` | - | LLM API Key |
| `OPENAI_API_BASE_URL` | `https://api.openai.com/v1` | LLM API 地址（支持兼容接口） |
| `OPENAI_MODEL_NAME` | `gpt-4o-mini` | 生成使用的模型名称 |
| `ADMIN_DEFAULT_PASSWORD` | `ChangeMe123!` | 管理员初始密码 |

### 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PROVIDER` | `mysql` | 数据库类型，当前仅支持 `mysql` |
| `MYSQL_HOST` | `host.docker.internal` | MySQL 主机 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_USER` | `arboris` | MySQL 用户名 |
| `MYSQL_PASSWORD` | - | MySQL 密码 |
| `MYSQL_DATABASE` | `arboris` | 数据库名 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址 |

### 嵌入模型（RAG 检索）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_PROVIDER` | `openai` | `openai` 或 `ollama` |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | 嵌入模型名称 |
| `EMBEDDING_BASE_URL` | 复用 `OPENAI_API_BASE_URL` | 嵌入模型 API 地址 |
| `EMBEDDING_API_KEY` | 复用 `OPENAI_API_KEY` | 嵌入模型 API Key |
| `EMBEDDING_MODEL_VECTOR_SIZE` | `3072` | 向量维度，需与模型匹配 |

### 向量数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VECTOR_DB_URL` | `file:./storage/rag_vectors.db` | libsql 向量库路径 |
| `VECTOR_TOP_K_CHUNKS` | `5` | RAG 检索返回的文本块数 |
| `VECTOR_TOP_K_SUMMARIES` | `3` | RAG 检索返回的摘要数 |
| `VECTOR_CHUNK_SIZE` | `480` | 文本分块大小（字符） |
| `VECTOR_CHUNK_OVERLAP` | `120` | 分块重叠大小 |
| `QDRANT_HOST` | `127.0.0.1` | Qdrant 地址（Mem0 使用） |
| `QDRANT_PORT` | `6333` | Qdrant 端口 |

### 生成参数

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WRITER_CHAPTER_VERSION_COUNT` | `2` | 每章生成的候选版本数 |
| `LLM_SSL_VERIFY` | `true` | SSL 验证，自签名证书可设 `false` |

### 功能开关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ALLOW_USER_REGISTRATION` | `false` | 是否开放注册 |
| `ENABLE_LINUXDO_LOGIN` | `false` | Linux.do 第三方登录 |
| `DEBUG` | `false` | 调试模式 |
| `LOGGING_LEVEL` | `INFO` | 日志级别：DEBUG/INFO/WARNING/ERROR |

---

## Go Gateway 配置

Go Gateway 使用 `gateway/config.yaml` 配置文件。生产环境中需确保以下项与后端一致：

```yaml
# JWT 密钥必须与后端 SECRET_KEY 一致
jwt:
  secret: "与后端 SECRET_KEY 相同的值"

# 后端地址
backend:
  fastapi_url: "http://app:8000"  # Docker 网络中用服务名

# Redis 地址
redis:
  addr: "redis:6379"  # Docker 网络中用服务名

# Task Dispatcher Worker 回调地址
task_dispatcher:
  worker_callback_url: "http://app:8000/api/internal/tasks"
```

Docker Compose 生产环境中也可通过环境变量覆盖：

```env
GATEWAY_SERVER_HOST=0.0.0.0
GATEWAY_SERVER_PORT=3000
GATEWAY_REDIS_ADDR=redis:6379
GATEWAY_JWT_SECRET=与SECRET_KEY相同
GATEWAY_BACKEND_FASTAPI_URL=http://app:8000
```

---

## 数据库管理

### 自动初始化

应用首次启动时 `init_db()` 会自动：
1. 检测数据库是否存在，不存在则创建
2. 创建所有 ORM 表结构（18 张表）
3. 创建默认管理员账户
4. 从 `backend/prompts/*.md` 加载提示词模板到数据库
5. 同步系统默认配置

### 索引优化

为提高查询性能，建议执行复合索引：

```bash
mysql -u arboris -p arboris < backend/migrations/add_composite_indexes.sql
```

### 备份

```bash
# 导出
mysqldump -u arboris -p arboris > backup_$(date +%Y%m%d).sql

# 恢复
mysql -u arboris -p arboris < backup_20260313.sql
```

---

## 日志与监控

### 日志位置

| 日志 | 路径 | 轮转策略 |
|------|------|---------|
| 应用日志 | `backend/logs/app.log` | 10MB x 5 份 |
| LLM 调用日志 | `backend/logs/llm.log` | 20MB x 10 份 |
| Gateway 日志 | stdout 或 `gateway/logs/gateway.log` | 按 config.yaml 配置 |
| Nginx 日志 | Docker 容器 stdout | Docker 日志轮转 |

### 监控端点

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 应用健康检查 |
| `GET /health` | Gateway 健康检查 |
| `GET /metrics` | Prometheus 指标（需 Gateway） |
| `http://localhost:5555` | Flower Celery 监控面板 |

### 查看日志

```bash
# Docker 部署
docker compose logs -f app           # 后端日志
docker compose logs -f gateway        # Gateway 日志
docker compose logs -f celery-worker-chapter  # Worker 日志

# 本地开发
tail -f backend/logs/app.log
tail -f backend/logs/llm.log
```

---

## 常见问题

### 1. 数据库连接失败

```
sqlalchemy.exc.OperationalError: Can't connect to MySQL server
```

- Docker 中连接宿主机 MySQL：`MYSQL_HOST=host.docker.internal`
- 确认 MySQL 允许远程连接
- 检查防火墙/安全组是否开放 3306

### 2. LLM API 超时

章节生成是长耗时操作（通常 1-5 分钟），确保：
- 网络能访问 LLM API 地址
- Vite 代理超时已设为 30 分钟（默认已配置）
- Nginx 的 `proxy_read_timeout` 已设为 300s（生产 nginx.conf 已配置）

### 3. 嵌入模型报错

```
Embedding generation failed
```

- 确认 `EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`、`EMBEDDING_BASE_URL` 配置正确
- 使用 Ollama 时确保 Ollama 服务已启动且模型已下载：`ollama pull nomic-embed-text`

### 4. Redis 连接失败

- 本地开发：确保 Redis 容器在运行（`docker ps | grep redis`）
- Docker 部署：使用服务名 `redis` 而非 `localhost`
- 需要密码时格式：`redis://:password@host:port/db`

### 5. Go Gateway 不生效

前端会自动检测 Gateway 可用性。如果前端仍使用 SSE 模式：
- 确认 Gateway 已启动：`curl http://localhost:3000/health`
- 确认 `config.yaml` 中 `jwt.secret` 与后端 `SECRET_KEY` 一致
- 检查 Nginx 路由是否正确转发 `/tasks/` 和 `/ws` 到 Gateway

### 6. 前端构建失败

```
error: Node.js version mismatch
```

确认 Node.js 版本：`node -v`，需要 `^20.19.0` 或 `>=22.12.0`。

### 7. 权限问题（Docker）

```
Permission denied: /app/storage
```

`docker-entrypoint.sh` 会自动修复权限。如果仍有问题：

```bash
docker compose exec app chown -R appuser:appuser /app/storage
```
