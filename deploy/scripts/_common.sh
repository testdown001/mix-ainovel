#!/usr/bin/env bash
# =============================================================================
# deploy/scripts 公共库：路径解析、彩色输出、Compose 命令解析、.env 加载。
#
# 用法（在同目录脚本内）：
#     SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#     . "$SCRIPT_DIR/_common.sh"
#
# 注意：server_deploy.sh 是「curl | bash」的引导脚本（跑的时候仓库还没克隆下来），
# 因此它必须自包含，不能 source 本文件。
# =============================================================================

# 颜色（非 TTY 时留空，避免日志里塞满转义序列）
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

info()  { echo -e "${BLUE}[*]${NC} $*"; }
ok()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
die()   { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ---- 路径（无论从哪个目录调用都能定位）---------------------------------------
_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$_COMMON_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$_COMMON_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

# 应用容器的服务名（生产栈与单容器栈都叫 app）
APP_SERVICE="${APP_SERVICE:-app}"

# ---- Compose 命令解析 --------------------------------------------------------
# 生产机通常只装 v2 插件（docker-compose-plugin），没有 v1 的 docker-compose 二进制；
# 老脚本里写死 `docker-compose` 会直接 command not found。这里统一解析成 DC 数组。
#
# 多 compose 文件用 docker 原生的 COMPOSE_FILE 环境变量（v1/v2 都认），例如：
#     COMPOSE_FILE=docker-compose.prod.yml:docker-compose.https.yml
resolve_compose() {
    if docker compose version >/dev/null 2>&1; then
        DC=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        DC=(docker-compose)
        warn "使用旧版 docker-compose(v1)，建议升级到 compose v2 插件"
    else
        die "未检测到 Docker Compose（既无 docker compose 插件，也无 docker-compose 二进制）"
    fi
}

require_docker() {
    command -v docker >/dev/null 2>&1 || die "未安装 Docker，见 https://docs.docker.com/get-docker/"
    resolve_compose
}

# dc <args...>：在 DEPLOY_DIR 下执行 compose 子命令（COMPOSE_FILE 里的相对路径才解析得到）
dc() {
    ( cd "$DEPLOY_DIR" && "${DC[@]}" "$@" )
}

# app_exec <cmd...>：在 app 容器里执行命令（-T：无 TTY，可在 CI / ssh 管道里跑）
app_exec() {
    dc exec -T "$APP_SERVICE" "$@"
}

# 当前生效的 compose 文件描述（仅用于日志）
compose_desc() {
    echo "${COMPOSE_FILE:-docker-compose.yml}"
}

# ---- .env 加载 ---------------------------------------------------------------
# 允许回落到仓库根 .env；统一去掉 CRLF（Windows 编辑过的 .env 会带 \r，会污染变量值）。
load_env() {
    if [ ! -f "$ENV_FILE" ] && [ -f "$PROJECT_ROOT/.env" ]; then
        ENV_FILE="$PROJECT_ROOT/.env"
    fi
    [ -f "$ENV_FILE" ] || die "未找到环境变量文件：$DEPLOY_DIR/.env（或 $PROJECT_ROOT/.env）"
    set -a
    # shellcheck disable=SC1090
    . <(tr -d '\r' < "$ENV_FILE")
    set +a
}

# require_env VAR...：校验必需变量已设置且非空
require_env() {
    local missing=0 var
    for var in "$@"; do
        if [ -z "${!var:-}" ]; then
            echo -e "${RED}[✗]${NC} 缺少环境变量：$var" >&2
            missing=1
        fi
    done
    [ "$missing" = 0 ] || die "请在 $ENV_FILE 中补全上述变量后重试"
}
