# ============================================
# 第一阶段：构建前端静态资源
# ============================================
# 运行时版本须与 .github/workflows/ci.yml 保持一致（Node 22 / Python 3.12），
# 否则 CI 绿灯并不代表镜像可构建/可运行。改这里请同步改 CI，反之亦然。
FROM node:22-slim AS frontend-builder

WORKDIR /frontend

# 配置 npm 使用中国镜像源
RUN npm config set registry https://registry.npmmirror.com

# 复制前端依赖文件
COPY frontend/package*.json ./

# 只用 npm ci：严格按 package-lock.json 安装，可复现。
# （先 npm install 再 npm ci 会先改写 lock 再整包重装，既慢一倍又破坏可复现性。）
RUN npm ci --prefer-offline --no-audit

# 复制前端源码
COPY frontend/ ./

# 构建前端
RUN npm run build

# ============================================
# 第二阶段：构建最终镜像（后端 + nginx）
# ============================================
FROM python:3.12-slim

# 配置 apt 使用中国镜像源。基础镜像换 Debian 大版本时 sources 文件形态可能变，
# 故加存在性判断：换不了镜像源顶多慢，不该让整个构建挂掉。
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
        sed -i 's|security.debian.org/debian-security|mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    fi

WORKDIR /app

# 安装系统依赖：nginx、supervisor、curl、mysql客户端等
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用中国镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端依赖文件
COPY backend/requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端应用代码
COPY backend/ ./

# 清理可能被带入的 SQLite 数据文件，确保首次启动时根据环境变量初始化管理员密码。
# 注意 sqlite_path 默认是 ./arboris.db（即 /app/arboris.db），不在 storage/ 下——
# 只删 storage/ 会漏掉它，开发机的库就会被打进镜像，首启带着旧 admin 行，
# ADMIN_DEFAULT_PASSWORD 反而不生效。这里连同 /app 下的散落 db 文件一起清掉。
RUN rm -rf /app/storage && mkdir -p /app/storage && rm -f /app/*.db /app/*.sqlite3

# 从前端构建阶段复制静态资源到 nginx 默认目录
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

# 复制部署配置
# 单容器：用自包含的 standalone 配置覆盖 nginx 主配置（uvicorn 监听 127.0.0.1:8000）。
# 生产栈不使用镜像内 nginx（改由独立 nginx 容器挂载 deploy/nginx.conf 做负载均衡）。
COPY deploy/nginx.standalone.conf /etc/nginx/nginx.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/docker-entrypoint.sh /app/docker-entrypoint.sh

# 允许入口脚本在启动时修正宿主机挂载目录权限
RUN chmod +x /app/docker-entrypoint.sh

# 创建非 root 用户（供 supervisor 使用）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 暴露端口（nginx 80端口）
EXPOSE 80

# 使用 supervisor 启动 nginx 和 uvicorn
# 注意：容器以 root 启动，supervisor 会根据配置降权运行各个进程
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
