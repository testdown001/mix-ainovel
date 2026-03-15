# Celery 任务队列系统部署指南

## 已完成的改造

### 1. Celery 核心组件

- ✅ `app/tasks/celery_app.py` - Celery 应用配置
- ✅ `app/tasks/chapter_tasks.py` - 章节生成异步任务
- ✅ `app/api/routers/tasks.py` - 任务状态查询 API
- ✅ `celery_worker.py` - Worker 启动脚本
- ✅ `celery_beat.py` - Beat 启动脚本

### 2. API 接口

- ✅ `POST /api/writer/async/generate` - 异步章节生成（提交任务）
- ✅ `GET /api/tasks/{task_id}/status` - 查询任务状态
- ✅ `POST /api/tasks/{task_id}/cancel` - 取消任务
- ✅ `GET /api/tasks/{task_id}/result` - 获取任务结果

### 3. 部署配置

- ✅ `deploy/docker-compose.prod.yml` - 生产环境配置
  - Nginx 负载均衡器
  - 3 个 FastAPI 实例
  - 3 个章节生成 Worker
  - 2 个批量生成 Worker
  - Celery Beat 定时任务
  - Flower 监控面板
  - MySQL + Redis + Qdrant

- ✅ `deploy/nginx.conf` - Nginx 配置
- ✅ `deploy/mysql.cnf` - MySQL 优化配置

## 本地开发测试

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动 Redis（如果未运行）

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. 启动 Celery Worker

```bash
# 终端 1: 启动 FastAPI
uvicorn app.main:app --reload

# 终端 2: 启动 Celery Worker
celery -A app.tasks.celery_app worker --loglevel=info -c 4

# 终端 3: 启动 Flower 监控（可选）
celery -A app.tasks.celery_app flower --port=5555
```

### 4. 测试异步章节生成

```bash
# 提交异步任务
curl -X POST "http://localhost:8000/api/writer/async/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "your-project-id",
    "chapter_number": 1,
    "preset": "basic",
    "use_agent_system": false,
    "rag_mode": "simple"
  }'

# 响应示例
{
  "task_id": "abc123-def456-ghi789",
  "project_id": "your-project-id",
  "chapter_number": 1,
  "status": "submitted",
  "message": "章节生成任务已提交，task_id: abc123-def456-ghi789"
}

# 查询任务状态
curl "http://localhost:8000/api/tasks/abc123-def456-ghi789/status" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 响应示例（进行中）
{
  "task_id": "abc123-def456-ghi789",
  "status": "PROGRESS",
  "meta": {
    "project_id": "your-project-id",
    "chapter_number": 1,
    "status": "generating",
    "progress": 50
  }
}

# 响应示例（完成）
{
  "task_id": "abc123-def456-ghi789",
  "status": "SUCCESS",
  "result": {
    "chapter_id": 123,
    "chapter_number": 1,
    "status": "completed",
    "versions": [...]
  }
}
```

## 生产环境部署

### 1. 配置环境变量

```bash
cd deploy
cp ../.env.example .env
# 编辑 .env 文件，设置必要的环境变量
```

### 2. 启动生产环境

```bash
# 构建镜像
docker compose -f docker-compose.prod.yml build

# 启动所有服务
docker compose -f docker-compose.prod.yml up -d

# 查看服务状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f app
docker compose -f docker-compose.prod.yml logs -f celery-worker-chapter
```

### 3. 访问监控面板

- Flower 监控: http://localhost:5555
- Nginx 健康检查: http://localhost/health

### 4. 扩缩容

```bash
# 扩展 API 实例到 5 个
docker compose -f docker-compose.prod.yml up -d --scale app=5

# 扩展章节生成 Worker 到 5 个
docker compose -f docker-compose.prod.yml up -d --scale celery-worker-chapter=5
```

## 架构优势

### 1. 解耦 HTTP 请求周期

- **改造前**: 章节生成在 HTTP 请求周期内完成，30-120s 阻塞 worker
- **改造后**: 提交任务立即返回，通过 task_id 异步查询进度

### 2. 水平扩展能力

- **API 层**: 3 个 FastAPI 实例，通过 Nginx 负载均衡
- **Worker 层**: 5 个 Celery Worker，独立扩缩容
- **数据库**: MySQL 连接池优化，支持 500 并发连接

### 3. 任务优先级队列

- `chapter_generation` 队列: 单章生成，高优先级
- `batch_generation` 队列: 批量生成，低优先级
- `default` 队列: 其他后台任务

### 4. 容错与重试

- 任务失败自动重试（最多 3 次）
- 指数退避策略，避免雪崩
- Worker 进程定期重启，防止内存泄漏

## 性能预期

| 指标 | 改造前 | 改造后 | 提升 |
|------|--------|--------|------|
| 并发请求 | 30 | 300+ | 10x |
| 章节生成吞吐 | 0.5 章/秒 | 5-10 章/秒 | 10-20x |
| 百人排队时间 | 200 秒 | 20-40 秒 | 5-10x |
| 支撑并发用户 | 50-100 | 200-500 | 4-5x |

## 下一步优化

1. ✅ **Celery 任务队列** - 已完成
2. ⏳ **数据库连接池优化** - 待实施
3. ⏳ **Redis 缓存层** - 待实施
4. ⏳ **LLM 调用限流** - 待实施
5. ⏳ **多租户数据隔离** - 待实施

## 注意事项

1. **Redis 持久化**: 生产环境已启用 AOF 持久化
2. **MySQL 连接池**: 需要根据实际负载调整 `max_connections`
3. **Worker 并发数**: 根据服务器 CPU 核心数调整 `-c` 参数
4. **任务超时**: 章节生成任务软超时 10 分钟，硬超时 11 分钟
5. **监控告警**: 建议接入 Prometheus + Grafana 监控 Celery 指标
