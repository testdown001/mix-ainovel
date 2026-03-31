# Arboris Go 服务部署文档

## 一、系统架构概览

```
                  ┌──────────────┐
                  │   Nginx LB   │ :80 / :443
                  └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              │                     │
     ┌────────▼────────┐   ┌───────▼────────┐
     │  Go Gateway     │   │  Go API Server │
     │  (arboris-gw)   │   │  (arboris-api) │
     │  :3000 反向代理  │   │  :3000 业务API  │
     └────────┬────────┘   └───────┬────────┘
              │                     │
     ┌────────▼─────────────────────▼────────┐
     │              Redis :6379               │
     │  (缓存 / 限流 / 分布式锁 / Pub/Sub /   │
     │   Streams MQ / Celery Broker)          │
     └────────┬──────────────────────────────┘
              │
     ┌────────▼─────────────────────┐
     │       MySQL 8.0 :3306        │
     │  (主库 + 可选读副本)          │
     └──────────────────────────────┘
              │
     ┌────────▼─────────────────────┐
     │  FastAPI (Python) :8000      │
     │  (LLM编排 / 章节生成 / RAG)   │
     └──────────────────────────────┘
```

Go 服务包含两个二进制文件：

| 二进制 | 入口 | 职责 |
|--------|------|------|
| `arboris-gateway` | `cmd/gateway/main.go` | API 网关：JWT 鉴权、限流、反向代理、WebSocket、任务分发 |
| `arboris-api` | `cmd/api/main.go` | 业务 API：认证、支付、项目查询、章节生成、配额管理 |

---

## 二、环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Go | 1.22 | 1.22+ |
| MySQL | 8.0 | 8.0.35+ |
| Redis | 6.0 | 7.0+ |
| Node.js | 18 | 20 (前端构建) |
| Python | 3.11 | 3.11 (FastAPI 后端) |
| Docker | 24.0 | 25.0+ |
| Docker Compose | 2.20 | 2.24+ |

---

## 三、快速启动（开发环境）

### 3.1 本地直接运行

```bash
# 1. 启动依赖服务
redis-server &
# MySQL 需要已启动并创建 arboris 数据库

# 2. 编译 Go 服务
cd gateway
make build-all

# 3. 启动 Gateway（反向代理模式）
./arboris-gateway

# 4. 启动 API Server（业务模式，需要 MySQL）
# 先编辑 config.yaml 将 database.enabled 设为 true
./arboris-api
```

### 3.2 使用 go run

```bash
# Gateway
make run

# API Server
make run-api
```

### 3.3 仅需 Redis（不启用 DB）

如果只运行 Gateway 模式（反向代理到 Python），无需 MySQL。`database.enabled: false` 时 API Server 也可启动，但支付/项目等 DB 相关功能将不可用。

---

## 四、配置说明

配置文件：`gateway/config.yaml`

所有配置项均可通过环境变量覆盖，格式为 `GATEWAY_` 前缀 + 大写路径，例如：

```bash
GATEWAY_SERVER_PORT=3000
GATEWAY_REDIS_ADDR=redis:6379
GATEWAY_DATABASE_ENABLED=true
GATEWAY_DATABASE_HOST=mysql
GATEWAY_JWT_SECRET=your-production-secret
```

### 4.1 核心配置项

```yaml
server:
  host: "0.0.0.0"
  port: 3000
  read_timeout: 10s
  write_timeout: 120s       # LLM 流式请求需要长超时
  prefork: false             # 生产环境建议开启（多进程）

backend:
  fastapi_url: "http://app:8000"  # Python FastAPI 地址
  timeout: 120s

jwt:
  secret: "必须修改为强密码"       # 与 Python 后端 SECRET_KEY 保持一致
  issuer: "arboris-gateway"
  audience: "arboris-api"
```

### 4.2 Redis 配置（支持三种模式）

```yaml
redis:
  mode: "standalone"              # standalone | sentinel | cluster

  # standalone 模式
  addr: "localhost:6379"
  password: ""
  db: 0
  pool_size: 100                  # 连接池大小
  min_idle: 20                    # 最小空闲连接

  # sentinel 模式（高可用）
  # mode: "sentinel"
  # master_name: "mymaster"
  # sentinel_addrs:
  #   - "sentinel1:26379"
  #   - "sentinel2:26379"
  #   - "sentinel3:26379"

  # cluster 模式（分片）
  # mode: "cluster"
  # addrs:
  #   - "node1:6379"
  #   - "node2:6379"
  #   - "node3:6379"
```

### 4.3 数据库配置（读写分离）

```yaml
database:
  enabled: true
  host: "mysql-writer"
  port: 3306
  user: "arboris"
  password: "your-password"
  name: "arboris"
  read_hosts:                     # 读副本，空则不启用读写分离
    - "mysql-reader1:3306"
    - "mysql-reader2:3306"
  writer_max_open: 50             # 写库最大连接数
  writer_max_idle: 10
  reader_max_open: 100            # 读库最大连接数（单个副本）
  reader_max_idle: 20
  slow_threshold: 200ms           # 慢查询阈值
  log_level: "warn"               # silent | error | warn | info
```

### 4.4 支付配置

```yaml
payment:
  enabled: true
  stripe_secret_key: "sk_live_xxx"
  stripe_webhook_secret: "whsec_xxx"
  success_url: "https://yourdomain.com/settings?tab=subscription&status=success"
  cancel_url: "https://yourdomain.com/settings?tab=subscription&status=cancel"
  webhook_workers: 4              # Webhook Worker Pool goroutine 数
  webhook_queue_size: 100         # channel 队列深度
```

### 4.5 限流配置

```yaml
rate_limit:
  default_rps: 10                 # 免费用户每秒请求数
  default_rpm: 60                 # 免费用户每分请求数
  default_concurrent: 3           # 免费用户最大并发
  premium_rps: 30                 # 付费用户每秒请求数
  premium_rpm: 180
  premium_concurrent: 8
```

---

## 五、Docker 部署

### 5.1 构建 Gateway 镜像

```bash
cd gateway
docker build -t arboris-gateway:latest .
```

需要同时构建 API Server 时，修改 `Dockerfile` 的 CMD 或使用多阶段构建：

```dockerfile
# 在 builder 阶段同时编译两个二进制
RUN CGO_ENABLED=0 GOOS=linux go build -o gateway cmd/gateway/main.go
RUN CGO_ENABLED=0 GOOS=linux go build -o api cmd/api/main.go
```

### 5.2 生产环境 Docker Compose

使用 `deploy/docker-compose.prod.yml`：

```bash
cd deploy

# 创建 .env 文件
cat > .env << 'EOF'
SECRET_KEY=your-strong-secret-key-at-least-32-chars
MYSQL_ROOT_PASSWORD=root-password
MYSQL_PASSWORD=arboris-password
ADMIN_DEFAULT_PASSWORD=AdminPass123!
OPENAI_API_KEY=sk-your-key
EOF

# 启动全部服务
docker compose -f docker-compose.prod.yml up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f gateway

# 扩容
docker compose -f docker-compose.prod.yml up -d --scale app=5 --scale celery-worker-chapter=5
```

### 5.3 服务依赖顺序

```
MySQL → Redis → Qdrant → FastAPI App → Go Gateway → Nginx
                                     → Celery Workers
                                     → Celery Beat
```

---

## 六、数据库迁移

### 6.1 自动迁移（GORM AutoMigrate）

API Server 启动时自动创建/更新表结构：
- `payment_orders`
- `subscriptions`

### 6.2 手动迁移（SQL 脚本）

```bash
# 索引优化 + 支付表 DDL
mysql -u arboris -p arboris < gateway/migrations/001_indexes_and_payment_tables.sql

# 分区（仅在数据量达到阈值后执行）
mysql -u arboris -p arboris < gateway/migrations/002_partitions.sql
```

### 6.3 分区策略

| 表 | 分区键 | 策略 | 触发条件 |
|----|--------|------|---------|
| `chapter_versions` | `id` | RANGE，每 500 万行 | 行数 > 300 万 |
| `payment_orders` | `created_at` | RANGE，按年 | 上线即可启用 |
| `writing_archives` | `created_at` | RANGE，按年 | 行数 > 100 万 |

---

## 七、监控与诊断

### 7.1 健康检查

```bash
# Gateway / API Server
curl http://localhost:3000/health

# 返回示例：
# {"success":true,"data":{"status":"ok","redis":"ok","database":"ok","time":"2026-03-27T..."}}
```

### 7.2 Prometheus 指标

```bash
curl http://localhost:3000/metrics
```

关键指标：

| 指标 | 说明 |
|------|------|
| `http_requests_total` | HTTP 请求总数（按 method/path/status） |
| `http_request_duration_seconds` | 请求延迟直方图 |
| `distributed_lock_acquired_total` | 分布式锁获取次数 |
| `distributed_lock_wait_seconds` | 锁等待时间 |
| `db_pool_open_connections` | 数据库连接池活跃连接 |
| `db_pool_wait_total` | 等待连接次数 |
| `webhook_processed_total` | Webhook 处理成功数 |
| `webhook_queue_depth` | Webhook 队列深度 |
| `go_goroutine_count` | goroutine 数量 |
| `go_heap_alloc_bytes` | 堆内存使用 |
| `go_gc_pause_total_ms` | GC 暂停总时间 |

### 7.3 运行时诊断

```bash
# Go 运行时快照（goroutine / 内存 / GC）
curl http://localhost:3000/debug/runtime | jq .

# 数据库连接池
curl http://localhost:3000/debug/db-pool | jq .

# Redis 连接池
curl http://localhost:3000/debug/redis-pool | jq .

# Webhook Worker Pool 状态
curl http://localhost:3000/debug/webhook-pool | jq .
```

### 7.4 Grafana 推荐 Dashboard

1. **HTTP 层**：QPS / 延迟 P99 / 错误率 / 状态码分布
2. **连接池**：DB Open/Idle/Wait / Redis Hits/Misses/Timeouts
3. **分布式锁**：获取/释放/超时 / 等待时间 P95
4. **Go Runtime**：goroutine 数 / 堆内存 / GC 暂停 / 栈使用
5. **支付**：订单创建 / 完成 / 退款 / Webhook 队列深度

---

## 八、性能调优

### 8.1 Go 服务调优

```bash
# 生产环境推荐环境变量
export GOMAXPROCS=0          # 自动使用所有 CPU
export GOGC=100              # GC 触发百分比（默认值，内存充裕可提高到 200）
```

代码层已内置的优化：
- **sync.Pool** 对象池（bytes.Buffer / []byte），0 allocs/op
- **singleflight** 防止缓存雪崩
- **L1 进程内缓存（5s）** + **L2 Redis 缓存（30min）** 两级缓存
- **semaphore** 限制 LLM 并发调用（默认 5）
- **goroutine 泄漏检测** 自动告警（阈值 500）

### 8.2 连接池推荐值

| 场景 | writer_max_open | reader_max_open | Redis pool_size |
|------|----------------|-----------------|-----------------|
| 开发环境 | 10 | 20 | 20 |
| 小规模（<1K 日活） | 20 | 50 | 50 |
| 中规模（1K-10K） | 50 | 100 | 100 |
| 大规模（>10K） | 100 | 200 | 200 |

### 8.3 压力测试

```bash
cd gateway

# 健康检查 1K 并发 30s
make loadtest-health

# 混合场景 500 并发 60s
make loadtest-mixed

# 10K 并发极限测试
make loadtest-10k

# 自定义测试
go run test/loadtest/main.go \
  -url http://localhost:3000 \
  -c 2000 \
  -d 60s \
  -scenario mixed \
  -token "your-jwt-token"
```

---

## 九、安全清单

- [ ] 修改 `jwt.secret` 为强随机字符串（>= 32 字符），与 Python `SECRET_KEY` 一致
- [ ] 设置 MySQL 强密码，禁止 root 远程登录
- [ ] Redis 设置 `requirepass`，绑定内网 IP
- [ ] 生产环境关闭 `/debug/*` 端点（通过 Nginx 限制访问或移除路由）
- [ ] Stripe Webhook 使用 HTTPS endpoint
- [ ] 配置 HTTPS（Nginx 层终止 TLS）
- [ ] 设置 `CORS` 仅允许生产域名
- [ ] 敏感配置通过环境变量注入，不要提交到 Git

---

## 十、API 端点一览

### 10.1 Gateway 端点（arboris-gateway）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus 指标 |
| ALL | `/api/*` | 反向代理到 FastAPI |
| WS | `/ws/:project_id` | WebSocket（实时进度） |

### 10.2 API Server 端点（arboris-api）

**认证**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v2/auth/users` | 注册 |
| POST | `/api/v2/auth/token` | 登录 |
| GET | `/api/v2/auth/users/me` | 当前用户 |
| PUT | `/api/v2/users/me/password` | 修改密码 |
| GET | `/api/v2/quota/me` | 配额查询 |

**项目 & 章节**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/novels` | 项目列表（分页） |
| GET | `/api/v2/novels/:id` | 完整项目数据（errgroup 并行查询） |
| GET | `/api/v2/novels/:id/sections/:section` | 局部数据 |
| GET | `/api/v2/novels/:id/chapters/:num` | 单章详情 |

**章节生成**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v2/writer/generate` | 同步生成 |
| POST | `/api/v2/writer/generate/stream` | SSE 流式生成 |
| POST | `/api/v2/writer/batch-generate` | 批量生成（Fan-out） |

**支付 & 订阅**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/plans/public` | 公开套餐列表 |
| POST | `/api/v2/payment/orders` | 创建订单 |
| GET | `/api/v2/payment/orders` | 订单列表 |
| GET | `/api/v2/payment/subscription` | 当前订阅 |
| POST | `/api/v2/payment/subscription/cancel` | 取消订阅 |
| POST | `/api/v2/admin/payment/orders/:id/refund` | 退款（管理员） |
| POST | `/api/v2/webhooks/stripe` | Stripe Webhook |

**调试（生产环境应限制访问）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/debug/runtime` | Go 运行时诊断 |
| GET | `/debug/db-pool` | DB 连接池 |
| GET | `/debug/redis-pool` | Redis 连接池 |
| GET | `/debug/webhook-pool` | Webhook 池状态 |

---

## 十一、常见问题

### Q: Gateway 和 API Server 需要同时运行吗？

不一定。两者可以独立部署：
- **仅 Gateway**：作为反向代理，所有请求转发到 Python FastAPI。无需 MySQL。
- **仅 API Server**：直接暴露 `/api/v2/*` 端点，提供认证、支付、项目查询等。需要 MySQL + Redis。
- **两者同时**：Gateway 处理限流/WebSocket/代理，API Server 处理业务逻辑。Nginx 根据路径分流。

### Q: 如何从 standalone Redis 切换到 Sentinel？

1. 部署 Redis Sentinel 集群（至少 3 个 Sentinel 节点）
2. 修改 `config.yaml`：
   ```yaml
   redis:
     mode: "sentinel"
     master_name: "mymaster"
     sentinel_addrs: ["s1:26379", "s2:26379", "s3:26379"]
   ```
3. 重启 Go 服务

### Q: 如何启用读写分离？

1. 搭建 MySQL 读副本（主从复制）
2. 修改 `config.yaml`：
   ```yaml
   database:
     read_hosts: ["reader1:3306", "reader2:3306"]
   ```
3. 重启 API Server。GORM `dbresolver` 自动将 SELECT 路由到读副本

### Q: Webhook 返回 429 怎么办？

说明 Worker Pool 队列已满。解决方案：
1. 增大 `payment.webhook_queue_size`（默认 100）
2. 增加 `payment.webhook_workers`（默认 4）
3. 检查 `/debug/webhook-pool` 确认 `processed` 和 `failed` 计数

### Q: goroutine 泄漏告警怎么办？

1. 检查 `/debug/runtime` 的 `num_goroutine` 字段
2. 使用 `pprof`（可在 `/debug/pprof/goroutine` 启用）查看泄漏堆栈
3. 常见原因：未关闭的 channel、未取消的 context、死循环 goroutine

---

## 十二、回滚与灾恢

```bash
# 使用部署脚本回滚
cd deploy/scripts
bash rollback.sh

# Docker 回滚到上一版本
docker compose -f docker-compose.prod.yml down
docker tag arboris-gateway:latest arboris-gateway:rollback
docker pull arboris-gateway:previous-tag
docker compose -f docker-compose.prod.yml up -d
```

数据库回滚注意事项：
- GORM AutoMigrate 只添加字段/索引，不会删除
- 分区操作（002_partitions.sql）不可逆，执行前务必备份
- 支付订单数据建议在操作前 `mysqldump` 备份
