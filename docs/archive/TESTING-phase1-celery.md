# Arboris-Novel 快速测试指南

## 前置条件

1. ✅ Celery 依赖已安装
2. ✅ Redis 正在运行
3. ✅ 数据库已配置

## 一、启动开发环境

### 方式 1: 使用启动脚本（推荐）

```bash
cd backend
./start-dev.sh
```

这会自动启动：
- FastAPI (端口 8000)
- Celery Worker (4 个并发)
- Flower 监控 (端口 5555)

### 方式 2: 手动启动

**终端 1 - FastAPI**:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

**终端 2 - Celery Worker**:
```bash
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info -c 4
```

**终端 3 - Flower 监控**:
```bash
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app flower --port=5555
```

## 二、验证服务状态

### 1. 检查 FastAPI

```bash
curl http://localhost:8000/api/health
```

预期响应:
```json
{
  "status": "healthy",
  "app": "AI Novel Generator API",
  "version": "1.0.0"
}
```

### 2. 检查 Flower 监控

浏览器访问: http://localhost:5555

应该能看到 Celery Worker 状态。

### 3. 检查 Redis

```bash
docker exec -it arboris-redis redis-cli ping
```

预期响应: `PONG`

## 三、测试异步章节生成

### 1. 获取认证 Token

```bash
# 登录获取 token
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

保存返回的 `access_token`。

### 2. 提交异步章节生成任务

```bash
export TOKEN="your_access_token_here"

curl -X POST "http://localhost:8000/api/writer/async/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "your-project-id",
    "chapter_number": 1,
    "preset": "basic",
    "use_agent_system": false,
    "rag_mode": "simple"
  }'
```

预期响应:
```json
{
  "task_id": "abc123-def456-ghi789",
  "project_id": "your-project-id",
  "chapter_number": 1,
  "status": "submitted",
  "message": "章节生成任务已提交，task_id: abc123-def456-ghi789"
}
```

### 3. 查询任务状态

```bash
export TASK_ID="abc123-def456-ghi789"

curl "http://localhost:8000/api/tasks/$TASK_ID/status" \
  -H "Authorization: Bearer $TOKEN"
```

任务状态变化:
- `PENDING` - 等待执行
- `PROGRESS` - 执行中
- `SUCCESS` - 成功完成
- `FAILURE` - 执行失败

### 4. 获取任务结果

```bash
curl "http://localhost:8000/api/tasks/$TASK_ID/result" \
  -H "Authorization: Bearer $TOKEN"
```

## 四、监控任务执行

### 1. Flower Web UI

访问 http://localhost:5555，可以看到：
- Worker 状态
- 任务队列长度
- 任务执行历史
- 实时任务监控

### 2. 查看日志

**FastAPI 日志**:
```bash
tail -f backend/logs/app.log
```

**LLM 调用日志**:
```bash
tail -f backend/logs/llm.log
```

**Celery Worker 日志**:
在 Celery Worker 终端查看实时输出。

## 五、测试限流功能

### 1. 测试 API 请求限流

快速发送多个请求，触发限流:

```bash
for i in {1..70}; do
  curl -s "http://localhost:8000/api/health" \
    -H "Authorization: Bearer $TOKEN" \
    -w "\nStatus: %{http_code}\n"
  sleep 0.5
done
```

当超过 60 req/min 时，会返回 429 状态码。

### 2. 测试 LLM Token 限流

提交多个章节生成任务，观察并发槽控制:

```bash
# 提交 5 个任务（超过默认 3 并发限制）
for i in {1..5}; do
  curl -X POST "http://localhost:8000/api/writer/async/generate" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"project_id\": \"test-project\",
      \"chapter_number\": $i,
      \"preset\": \"basic\"
    }" &
done
wait
```

在 Flower 中观察，最多只有 3 个任务同时执行。

## 六、测试数据库连接池

### 1. 查看连接池状态

```bash
# 在 Python 中查看
python -c "
from app.db.session import engine
print(f'Pool size: {engine.pool.size()}')
print(f'Checked out: {engine.pool.checkedout()}')
print(f'Overflow: {engine.pool.overflow()}')
"
```

### 2. 压力测试

使用 Apache Bench 或 wrk 进行压测:

```bash
# 安装 Apache Bench
sudo apt-get install apache2-utils

# 100 并发，1000 请求
ab -n 1000 -c 100 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/health
```

观察数据库连接池是否耗尽。

## 七、常见问题排查

### 问题 1: Celery Worker 无法连接 Redis

**症状**: Worker 启动失败，提示 `ConnectionError`

**解决**:
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 检查 Redis 连接
redis-cli -h localhost -p 6379 ping

# 检查环境变量
echo $REDIS_URL
```

### 问题 2: 任务一直处于 PENDING 状态

**症状**: 任务提交后状态不变

**解决**:
```bash
# 检查 Celery Worker 是否运行
ps aux | grep celery

# 检查 Worker 日志
# 查看是否有错误信息

# 重启 Worker
pkill -f celery
celery -A app.tasks.celery_app worker --loglevel=info -c 4
```

### 问题 3: 数据库连接池耗尽

**症状**: 请求超时，日志显示 `QueuePool limit exceeded`

**解决**:
```bash
# 增加连接池大小（临时）
# 编辑 app/db/session.py
# pool_size=20 → pool_size=40
# max_overflow=40 → max_overflow=80

# 或者减少并发请求数
```

### 问题 4: LLM API 限流触发

**症状**: 任务失败，提示 `Token 配额获取超时`

**解决**:
```python
# 调整限流参数
# 编辑 app/services/rate_limiter.py
# default_tpm=100000 → default_tpm=200000
# default_concurrent=3 → default_concurrent=5
```

## 八、停止服务

### 使用停止脚本

```bash
cd backend
./stop-dev.sh
```

### 手动停止

```bash
# 停止 tmux 会话
tmux kill-session -t arboris

# 停止 Redis
docker stop arboris-redis
docker rm arboris-redis

# 或者 Ctrl+C 停止各个终端的进程
```

## 九、下一步

1. ✅ 验证异步章节生成功能正常
2. ⏳ 实施 Redis 缓存层
3. ⏳ 实施多租户数据隔离
4. ⏳ 进行压力测试，验证性能提升

## 十、相关文档

- [Celery 部署指南](./celery-deployment-guide.md)
- [Phase 1 改造总结](../docs/phase1-改造总结.md)
- [多人并发架构调研报告](../docs/多人并发架构调研报告.md)
