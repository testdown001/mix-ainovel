#!/usr/bin/env bash
# =============================================================================
# Arboris-Novel 生产栈 + HTTPS 一键部署脚本（Ubuntu 22.04/24.04 LTS）
# =============================================================================
#
# 部署形态：生产栈（Nginx LB + Go 网关 + app + 自带 MySQL/Redis/Qdrant），HTTPS。
#
# 用法（在服务器上，仓库根目录或 deploy/ 下，以 root 或 sudo 运行）：
#     sudo bash deploy/scripts/oneclick_prod_https.sh
#
#   可选：用环境变量预设以实现完全非交互（不设则脚本会逐项询问）：
#     DOMAIN=novel.example.com \
#     LE_EMAIL=you@example.com \
#     OPENAI_API_KEY=sk-xxx \
#     OPENAI_API_BASE_URL=https://api.openai.com/v1 \
#     OPENAI_MODEL_NAME=gpt-4o-mini \
#     sudo -E bash deploy/scripts/oneclick_prod_https.sh
#
# 前置条件（脚本会检查/提示，但无法替你完成）：
#   1) 域名 A 记录已解析到本机公网 IP（certbot 签证书要靠这个验证）。
#   2) 云安全组 / 防火墙已放行 80 与 443。
#   3) 代码已在服务器上（私有仓库 git@github.com:leanb525/mix-ainovel.git，
#      git clone 需先在服务器配好 GitHub deploy key；或从本地 rsync 上来）。
#
# 本脚本做了什么（关键）：
#   · 装 Docker(含 compose 插件) + certbot；
#   · 生成 deploy/.env（随机生成所有密钥；幂等：已存在则不覆盖）；
#   · certbot standalone 预签发证书（此刻 Docker 未起，80 空闲）；
#   · 生成 HTTPS 版 nginx 配置 + compose override，并【修正生产栈一处装配缺陷】：
#       仓库 prod.yml 的上游都连 app:8000，但 app 容器内 uvicorn 只绑 127.0.0.1:8000，
#       跨容器须走容器内 nginx 的 80 端口。脚本把外层 LB upstream 与网关 fastapi_url
#       统一改连 app:80，否则生产栈起不来。（不改仓库跟踪文件，仅经 override/生成配置覆盖。）
#   · docker compose up -d --build 起栈；
#   · 装 certbot 自动续期 cron（续期瞬间停启 nginx 让出 80）。
#
# 注意：prod.yml 里的 deploy.replicas(gateway×2/app×3) 是 Swarm 语法，
#       普通 `docker compose up` 只起单副本。要真多副本请改用 `docker stack deploy`。
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[*]${NC} $*"; }
ok()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
die()   { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ---- 路径解析（脚本无论从哪运行都能定位 deploy/ 与仓库根）----------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
PROD_COMPOSE="$DEPLOY_DIR/docker-compose.prod.yml"
HTTPS_COMPOSE="$DEPLOY_DIR/docker-compose.https.yml"
HTTPS_NGINX="$DEPLOY_DIR/nginx.prod.https.conf"
WEBROOT_DIR="$DEPLOY_DIR/certbot-webroot"

[ -f "$PROD_COMPOSE" ] || die "未找到 $PROD_COMPOSE。请在已获取代码的仓库内运行本脚本。"

# ---- 0. 权限与基础命令 --------------------------------------------------------
[ "$(id -u)" = "0" ] || die "请用 root 运行：sudo bash $0"

echo "========================================="
echo " Arboris-Novel 生产栈 + HTTPS 一键部署"
echo "========================================="
info "系统：$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || uname -a)"

# ---- 1. 收集配置（环境变量优先，否则交互询问）---------------------------------
prompt() {  # prompt VAR "提示语" [默认值]
  local _var="$1" _msg="$2" _def="${3:-}" _cur="${!1:-}" _input
  if [ -n "$_cur" ]; then return; fi
  if [ -n "$_def" ]; then
    read -r -p "$_msg [$_def]: " _input || true
    printf -v "$_var" '%s' "${_input:-$_def}"
  else
    while [ -z "${_input:-}" ]; do read -r -p "$_msg: " _input || true; done
    printf -v "$_var" '%s' "$_input"
  fi
}

info "请填写部署参数（已通过环境变量预设的项会自动跳过）"
prompt DOMAIN              "对外域名（已解析到本机公网 IP）"
prompt LE_EMAIL            "Let's Encrypt 通知邮箱（到期提醒；某些域名的邮箱会被 LE 拒绝，可填 none 不绑邮箱）"
prompt OPENAI_API_KEY      "LLM API Key（不填则填占位，部署后可在后台改，但无法生成章节）" "sk-PLACEHOLDER-replace-me"
prompt OPENAI_API_BASE_URL "LLM API Base URL" "https://api.openai.com/v1"
prompt OPENAI_MODEL_NAME   "LLM 模型名" "gpt-4o-mini"

# 简单校验域名格式
echo "$DOMAIN" | grep -qE '^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' || die "域名格式可疑：$DOMAIN"

# ---- 2. 安装 Docker + certbot -------------------------------------------------
info "检查并安装系统依赖…"
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  info "安装 Docker（官方脚本，含 compose 插件）…"
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker compose version >/dev/null 2>&1 || {
  warn "未检测到 docker compose 插件，尝试 apt 安装…"
  apt-get update -y && apt-get install -y docker-compose-plugin
}
command -v certbot >/dev/null 2>&1 || { apt-get update -y && apt-get install -y certbot; }
command -v curl    >/dev/null 2>&1 || { apt-get update -y && apt-get install -y curl; }
ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) / compose / certbot 就绪"

# 防火墙提示（不擅自改规则，仅在 ufw active 时提示放行）
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  warn "检测到 ufw 已启用。确保已放行 80/443："
  echo "    ufw allow 80/tcp && ufw allow 443/tcp"
fi

# ---- 3. 生成 deploy/.env（幂等：存在则保留，仅校验必需键）----------------------
gen() { openssl rand -hex 32; }
if [ ! -f "$ENV_FILE" ]; then
  info "生成 $ENV_FILE（随机密钥）…"
  ADMIN_PW="Admin-$(openssl rand -hex 6)"
  ADMIN_EMAIL="$LE_EMAIL"; case "${LE_EMAIL,,}" in ""|none|skip) ADMIN_EMAIL="admin@${DOMAIN}" ;; esac
  cat > "$ENV_FILE" <<ENVEOF
# 由 oneclick_prod_https.sh 生成 —— 含密钥，请勿提交到 git（deploy/.env 已在 .gitignore）。
# 应用
SECRET_KEY=$(gen)
ENVIRONMENT=production
DEBUG=false
LOGGING_LEVEL=INFO
FORCE_HTTPS_REDIRECT=false
CORS_ORIGINS=https://${DOMAIN}

# 生产栈内部任务回调密钥（网关↔后端，两侧自动一致）
TASK_DISPATCHER_INTERNAL_CALLBACK_SECRET=$(gen)

# 数据库（生产栈自带 MySQL 容器，host 指向容器服务名 mysql）
DB_PROVIDER=mysql
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=arboris
MYSQL_PASSWORD=$(gen)
MYSQL_ROOT_PASSWORD=$(gen)
MYSQL_DATABASE=arboris

# Redis（生产栈自带）
REDIS_URL=redis://redis:6379/0

# 管理员（首次启动创建；请登录后立即修改）
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=${ADMIN_PW}
ADMIN_DEFAULT_EMAIL=${ADMIN_EMAIL}

# LLM / 嵌入
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_API_BASE_URL=${OPENAI_API_BASE_URL}
OPENAI_MODEL_NAME=${OPENAI_MODEL_NAME}
WRITER_CHAPTER_VERSION_COUNT=1
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=${OPENAI_API_BASE_URL}
EMBEDDING_API_KEY=${OPENAI_API_KEY}
EMBEDDING_MODEL=text-embedding-3-large

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# 注册开关
ALLOW_USER_REGISTRATION=false
ENVEOF
  chmod 600 "$ENV_FILE"
  ok ".env 已生成。管理员初始密码：${YELLOW}${ADMIN_PW}${NC}（登录后请立即修改）"
else
  warn ".env 已存在，保留不覆盖。校验必需键…"
  for k in SECRET_KEY TASK_DISPATCHER_INTERNAL_CALLBACK_SECRET MYSQL_PASSWORD MYSQL_ROOT_PASSWORD ADMIN_DEFAULT_PASSWORD OPENAI_API_KEY; do
    grep -qE "^${k}=.+" "$ENV_FILE" || die ".env 缺少必需键 $k，请补全后重跑。"
  done
  ok ".env 必需键齐全"
fi

# ---- 4. 签发 TLS 证书（certbot standalone，需 80 空闲）-------------------------
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [ -f "${CERT_DIR}/fullchain.pem" ]; then
  ok "证书已存在：${CERT_DIR}（跳过签发）"
else
  info "签发证书前先释放 80 端口（停掉可能在跑的 nginx 容器）…"
  (cd "$DEPLOY_DIR" && docker compose -f "$PROD_COMPOSE" stop nginx >/dev/null 2>&1) || true
  if ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE '[:.]80$'; then
    die "80 端口仍被占用，certbot 无法验证。请释放后重跑（ss -ltnp | grep :80 查占用）。"
  fi
  info "certbot 签发 ${DOMAIN} …（确保域名已解析到本机、80/443 已放行）"
  # 邮箱注册参数：填 none/skip/空则不绑邮箱（某些域名邮箱会被 LE 判定无效而拒绝注册）。
  CERTBOT_REG=(-m "$LE_EMAIL")
  case "${LE_EMAIL,,}" in ""|none|skip) CERTBOT_REG=(--register-unsafely-without-email) ;; esac
  certbot certonly --standalone --non-interactive --agree-tos "${CERTBOT_REG[@]}" -d "$DOMAIN" \
    || die "证书签发失败。常见原因：①邮箱被 LE 判定无效 → 换邮箱，或重跑时设 LE_EMAIL=none 跳过绑定；②域名未解析到本机（dig +short $DOMAIN）；③80 未放行；④触发 LE 频率限制。详见 /var/log/letsencrypt/letsencrypt.log"
  ok "证书签发成功：${CERT_DIR}"
fi
mkdir -p "$WEBROOT_DIR"

# ---- 5. 生成 HTTPS nginx 配置（占位符 __DOMAIN__ 由 sed 替换，避免 $ 被 shell 展开）----
info "生成 $HTTPS_NGINX（修正上游为 app:80）…"
cat > "$HTTPS_NGINX" <<'NGINXEOF'
# 自动生成（oneclick_prod_https.sh）—— 生产栈 HTTPS 版，请勿手改。
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;
events { worker_connections 4096; use epoll; multi_accept on; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on; tcp_nopush on; tcp_nodelay on; keepalive_timeout 65;
    types_hash_max_size 2048; client_max_body_size 100M;
    gzip on; gzip_vary on; gzip_proxied any; gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json
               application/javascript application/xml+rss image/svg+xml;

    upstream go_gateway     { least_conn; server gateway:3000 max_fails=3 fail_timeout=30s; keepalive 64; }
    # 关键修正：app 容器内 uvicorn 绑 127.0.0.1:8000，跨容器须走容器内 nginx 的 80 端口。
    upstream fastapi_backend { least_conn; server app:80 max_fails=3 fail_timeout=30s; keepalive 32; }

    # HTTP：放行 ACME 续期校验，其余 301 跳 HTTPS。
    server {
        listen 80;
        server_name __DOMAIN__;
        location /.well-known/acme-challenge/ { root /var/www/certbot; }
        location / { return 301 https://$host$request_uri; }
    }

    server {
        listen 443 ssl;
        http2 on;
        server_name __DOMAIN__;

        ssl_certificate     /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 10m;

        location /health  { access_log off; proxy_pass http://go_gateway; proxy_http_version 1.1; proxy_set_header Connection ""; }
        location /metrics { access_log off; proxy_pass http://go_gateway; proxy_http_version 1.1; proxy_set_header Connection ""; }

        location /ws {
            proxy_pass http://go_gateway;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }
        location /tasks/ {
            proxy_pass http://go_gateway;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header Connection "";
            proxy_read_timeout 30s;
        }
        location /api/ {
            proxy_pass http://go_gateway;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header Connection "";
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_cache off;
            proxy_set_header X-Accel-Buffering no;
        }
        location / {
            proxy_pass http://fastapi_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
        }
    }
}
NGINXEOF
sed -i "s/__DOMAIN__/${DOMAIN}/g" "$HTTPS_NGINX"
ok "nginx 配置已生成"

# ---- 6. 生成 compose override（HTTPS 挂载 + 修正网关上游 + 后端 HTTPS 信任）-----
info "生成 $HTTPS_COMPOSE …"
cat > "$HTTPS_COMPOSE" <<OVREOF
# 自动生成（oneclick_prod_https.sh）—— 叠加在 docker-compose.prod.yml 之上，启用 HTTPS 并修正接线。
services:
  app:
    deploy:
      replicas: 1            # 单副本：避免多副本并发跑 init_db 建表撞 DDL（错误 1684）
    environment:
      FORCE_HTTPS_REDIRECT: "false"   # nginx 已做 80→443 跳转，app 层不再重定向（否则容器内 HTTP 健康探针被 307）
      CORS_ORIGINS: "https://${DOMAIN}"
  gateway:
    deploy:
      replicas: 1            # nginx 上游 server gateway:3000 静态解析只连一个，多副本无意义
    environment:
      # 关键修正：网关反代目标改为 app 容器内 nginx(80)，而非绑回环的 uvicorn(8000)。
      GATEWAY_BACKEND_FASTAPI_URL: "http://app:80"
      GATEWAY_TASK_DISPATCHER_WORKER_CALLBACK_URL: "http://app:80/api/internal/tasks"
  nginx:
    volumes:
      - ./nginx.prod.https.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./certbot-webroot:/var/www/certbot:ro
OVREOF
ok "override 已生成"

COMPOSE=(docker compose -f "$PROD_COMPOSE" -f "$HTTPS_COMPOSE")

# ---- 7. 校验 compose 装配 -----------------------------------------------------
info "校验 compose 装配（docker compose config）…"
(cd "$DEPLOY_DIR" && "${COMPOSE[@]}" config -q) || die "compose 配置校验失败，请检查 .env 必需变量是否齐全。"
ok "compose 装配有效"

# ---- 8. 构建并启动 ------------------------------------------------------------
warn "即将构建镜像（前端 npm build + 后端 pip + Go 网关），首次约需数分钟…"
(cd "$DEPLOY_DIR" && "${COMPOSE[@]}" up -d --build) || die "启动失败，查看日志：cd $DEPLOY_DIR && ${COMPOSE[*]} logs"
ok "容器已启动"

# ---- 9. 健康检查（直连 app 容器内 uvicorn，最可靠）-----------------------------
info "等待应用就绪（MySQL 初始化 + app 启动，最多约 3 分钟）…"
HEALTHY=false
for i in $(seq 1 60); do
  if (cd "$DEPLOY_DIR" && "${COMPOSE[@]}" exec -T app curl -fs http://127.0.0.1:8000/api/health >/dev/null 2>&1); then
    HEALTHY=true; break
  fi
  sleep 3
done
if [ "$HEALTHY" = true ]; then
  ok "后端健康检查通过"
else
  warn "后端健康检查超时。查看日志定位："
  echo "    cd $DEPLOY_DIR && ${COMPOSE[*]} logs --tail=80 app mysql gateway"
fi

# 外部 HTTPS 连通性（容忍失败，仅作提示）
if curl -fsk --max-time 10 "https://localhost/api/health" >/dev/null 2>&1; then
  ok "HTTPS 链路连通（nginx→网关→app）"
else
  warn "本机 HTTPS 自检未通过（可能仍在启动 / 证书 SNI）。请用域名验证：curl https://${DOMAIN}/api/health"
fi

# ---- 10. 安装证书自动续期（续期瞬间停启 nginx 让出 80）-------------------------
CRON_FILE="/etc/cron.d/arboris-certbot-renew"
info "安装证书自动续期任务：$CRON_FILE"
cat > "$CRON_FILE" <<CRONEOF
# Arboris 证书续期（每日 03:17 尝试；仅在临近到期时实际续）。续期瞬间停启 nginx 让出 80 给 standalone 验证。
17 3 * * * root certbot renew --quiet --standalone \\
  --pre-hook  "cd $DEPLOY_DIR && docker compose -f $PROD_COMPOSE -f $HTTPS_COMPOSE stop nginx" \\
  --post-hook "cd $DEPLOY_DIR && docker compose -f $PROD_COMPOSE -f $HTTPS_COMPOSE start nginx"
CRONEOF
chmod 644 "$CRON_FILE"
ok "续期任务已安装"

# ---- 完成 ---------------------------------------------------------------------
echo ""
echo "========================================="
ok   "部署完成！"
echo "========================================="
echo ""
echo "  访问地址：   https://${DOMAIN}"
echo "  健康检查：   https://${DOMAIN}/api/health"
echo "  管理员：     用户名 admin（密码见上方 .env 生成提示 / cat $ENV_FILE）"
echo ""
echo "  常用命令（在 $DEPLOY_DIR 下）："
echo "    查看状态： ${COMPOSE[*]} ps"
echo "    查看日志： ${COMPOSE[*]} logs -f app gateway nginx"
echo "    重启：     ${COMPOSE[*]} restart"
echo "    停止：     ${COMPOSE[*]} down"
echo "    更新代码后重建： git pull && ${COMPOSE[*]} up -d --build"
echo ""
warn "提醒：① 登录后立即修改管理员密码；② 若用了占位 OPENAI_API_KEY，请在后台「API 管理」填真实 Key 后才能生成章节；"
warn "      ③ prod.yml 的 replicas 是 Swarm 语法，本脚本用普通 compose 起的是单副本。"
