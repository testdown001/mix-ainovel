#!/usr/bin/env bash
# =============================================================================
# 服务器端引导部署脚本（单容器栈，首次开机用）
#
# 本脚本是「curl | bash」的引导入口：跑的时候仓库可能还没克隆下来，
# 因此它必须自包含，不 source deploy/scripts/_common.sh。
#
# 用法（在服务器上以 root 执行）：
#     REPO_URL=git@github.com:you/your-repo.git \
#       bash <(curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/scripts/server_deploy.sh)
#
#   或代码已在服务器上时直接：
#     REPO_URL=... bash deploy/scripts/server_deploy.sh
#
# 变量：
#   REPO_URL(首次克隆必填) PROJECT_DIR(默认 /root/arboris-novel) GIT_BRANCH(默认 main)
#   ADMIN_DEFAULT_PASSWORD(默认随机生成并打印) APP_PORT(默认 80)
#
# 生产环境（HTTPS + Go 网关 + 独立 MySQL/Redis/Qdrant）请改用：
#     deploy/scripts/oneclick_prod_https.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[*]${NC} $*"; }
ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

PROJECT_DIR="${PROJECT_DIR:-/root/arboris-novel}"
GIT_BRANCH="${GIT_BRANCH:-main}"
REPO_URL="${REPO_URL:-}"
APP_PORT="${APP_PORT:-80}"

echo "========================================="
echo " Arboris-Novel 服务器端引导部署"
echo "========================================="

# ---- 1. 环境检查 --------------------------------------------------------------
[ "$(id -u)" = "0" ] || die "需要 root 权限"
info "系统：$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || uname -a)"

# ---- 2. 基础软件 --------------------------------------------------------------
info "检查基础软件…"
command -v git >/dev/null 2>&1 || { apt-get update -y && apt-get install -y git; }
command -v curl >/dev/null 2>&1 || apt-get install -y curl
command -v openssl >/dev/null 2>&1 || apt-get install -y openssl

if ! command -v docker >/dev/null 2>&1; then
    info "安装 Docker…"
    curl -fsSL https://get.docker.com | bash
    systemctl enable --now docker
fi
if docker compose version >/dev/null 2>&1; then
    DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    DC=(docker-compose)
else
    info "安装 docker compose 插件…"
    apt-get update -y && apt-get install -y docker-compose-plugin
    DC=(docker compose)
fi
ok "git / curl / docker / compose 就绪"

# ---- 3. 代码 ------------------------------------------------------------------
info "获取项目代码…"
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR"
    git fetch origin "$GIT_BRANCH"
    git reset --hard "origin/$GIT_BRANCH"
    ok "代码已更新到 origin/$GIT_BRANCH（$(git log --oneline -1)）"
else
    [ -n "$REPO_URL" ] || die "$PROJECT_DIR 下没有仓库，请提供 REPO_URL 供首次克隆"
    mkdir -p "$(dirname "$PROJECT_DIR")"
    git clone -b "$GIT_BRANCH" "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    ok "已克隆到 $PROJECT_DIR"
fi

DEPLOY_DIR="$PROJECT_DIR/deploy"
ENV_FILE="$DEPLOY_DIR/.env"

# ---- 4. 环境变量（幂等：已存在不覆盖）-----------------------------------------
info "准备环境变量…"
if [ -f "$ENV_FILE" ]; then
    ok "$ENV_FILE 已存在，保留不覆盖"
    ADMIN_PW_NOTE="（见 $ENV_FILE 中的 ADMIN_DEFAULT_PASSWORD）"
else
    # 默认管理员口令随机生成——绝不写死在脚本里（旧版固定 Admin123456! 等于公开凭据）。
    ADMIN_PW="${ADMIN_DEFAULT_PASSWORD:-Admin-$(openssl rand -hex 8)}"
    mkdir -p "$DEPLOY_DIR"
    cat > "$ENV_FILE" <<ENVEOF
# 由 server_deploy.sh 生成 —— 含密钥，切勿提交（deploy/.env 已在 .gitignore）。
# 应用
SECRET_KEY=$(openssl rand -hex 32)
ENVIRONMENT=production
DEBUG=false
LOGGING_LEVEL=INFO
APP_PORT=${APP_PORT}

# 数据库（默认 SQLite，零配置；换 MySQL 改 DB_PROVIDER=mysql 并启用 mysql profile）
DB_PROVIDER=sqlite
SQLITE_PATH=storage/arboris.db
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_USER=arboris
MYSQL_PASSWORD=$(openssl rand -hex 24)
MYSQL_DATABASE=arboris
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)

# 管理员（首启创建；登录后请立即修改）
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=${ADMIN_PW}
ADMIN_DEFAULT_EMAIL=admin@example.com

# LLM（运行时以后台「接口管理」的 SystemConfig 为准，这里只是首启种子）
OPENAI_API_KEY=sk-PLACEHOLDER-replace-me
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini
WRITER_CHAPTER_VERSION_COUNT=1

# 嵌入
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-PLACEHOLDER-replace-me
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_MODEL_VECTOR_SIZE=3072

# 向量库（Qdrant；单容器栈的 compose 已带 qdrant 服务）
QDRANT_HOST=qdrant
QDRANT_PORT=6333
VECTOR_TOP_K_CHUNKS=5
VECTOR_TOP_K_SUMMARIES=3
VECTOR_CHUNK_SIZE=480
VECTOR_CHUNK_OVERLAP=120

# 注册与登录
ALLOW_USER_REGISTRATION=true
ENABLE_LINUXDO_LOGIN=false
ENVEOF
    chmod 600 "$ENV_FILE"
    ok "$ENV_FILE 已生成（权限 600）"
    warn "管理员初始密码：${ADMIN_PW}"
    warn "请编辑 $ENV_FILE 填入真实 LLM Key（或部署后在后台「接口管理」配置）"
    ADMIN_PW_NOTE="（初始密码见上方输出）"
fi

# ---- 5. 构建并启动 ------------------------------------------------------------
info "构建并启动容器（首次约需数分钟）…"
cd "$DEPLOY_DIR"
"${DC[@]}" down 2>/dev/null || true
"${DC[@]}" up -d --build
ok "容器已启动"

# ---- 6. 健康检查 --------------------------------------------------------------
info "等待服务就绪（最多约 3 分钟）…"
HEALTHY=false
for _ in $(seq 1 90); do
    # </dev/null 尤其关键：本脚本支持 `curl … | bash`，此时 stdin 就是脚本本身，
    # docker exec 一旦接管 stdin 就会把后半段脚本吞掉。
    if "${DC[@]}" exec -T app curl -fs http://127.0.0.1:8000/api/health </dev/null >/dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 2
done

if [ "$HEALTHY" != true ]; then
    warn "健康检查未通过，最近日志："
    "${DC[@]}" logs --tail=50 app || true
    die "部署失败。常见原因：端口 ${APP_PORT} 被占用 / 数据库配置错误 / 依赖安装失败"
fi
ok "健康检查通过"

# ---- 完成 ---------------------------------------------------------------------
echo ""
echo "========================================="
ok "部署成功"
echo "========================================="
echo ""
echo "  前端：    http://$(curl -fsS --max-time 5 ifconfig.me 2>/dev/null || echo localhost):${APP_PORT}"
echo "  健康检查：/api/health"
echo "  管理员：  admin ${ADMIN_PW_NOTE}"
echo ""
echo "  常用命令（在 $DEPLOY_DIR 下）："
echo "    日志：${DC[*]} logs -f app"
echo "    重启：${DC[*]} restart"
echo "    停止：${DC[*]} down"
echo ""
warn "① 登录后立即修改管理员密码；② 用占位 Key 的话需在后台「接口管理」填真实 Key 才能生成章节"
echo ""
echo "完整部署说明：$PROJECT_DIR/DEPLOYMENT_GUIDE_FULL.md"
