#!/usr/bin/env bash
# =============================================================================
# 一键远程部署脚本（从本机 ssh 到目标服务器拉代码并重建容器）
#
# 目标服务器不写死在脚本里。两种给法（环境变量优先）：
#
#   1) 环境变量：
#        SERVER_IP=1.2.3.4 REPO_URL=git@github.com:you/your-repo.git \
#          bash deploy/scripts/quick_deploy.sh
#
#   2) 本机默认值文件 deploy/.deploy-target（已在 .gitignore，不会提交）：
#        SERVER_IP=1.2.3.4
#        SERVER_USER=root
#        PROJECT_DIR=/root/arboris-novel
#        REPO_URL=git@github.com:you/your-repo.git
#        GIT_BRANCH=main
#        COMPOSE_FILE=docker-compose.prod.yml   # 生产栈；单容器栈不填
#
# 全部可用变量：
#   SERVER_IP(必填) SERVER_USER(默认 root) SSH_PORT(默认 22)
#   PROJECT_DIR(默认 /root/arboris-novel) REPO_URL(仅首次克隆需要) GIT_BRANCH(默认 main)
#   COMPOSE_FILE  RUN_MIGRATIONS(默认 0)  NO_CACHE(默认 0)  ASSUME_YES(默认 0，=1 跳过确认)
#
# 前置：本机到服务器的 ssh 免密（密钥）已配好；服务器上 deploy/.env 已就绪。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/_common.sh
. "$SCRIPT_DIR/_common.sh"

# 本机默认值（环境变量已给的项不覆盖）。只认下面这几个键——写错了会当场提示，
# 也不会因为文件里一行奇怪内容就去 export 任意变量（比如覆盖 PATH）。
TARGET_KEYS="SERVER_IP SERVER_USER SSH_PORT PROJECT_DIR REPO_URL GIT_BRANCH COMPOSE_FILE RUN_MIGRATIONS NO_CACHE ASSUME_YES"
TARGET_FILE="$DEPLOY_DIR/.deploy-target"
if [ -f "$TARGET_FILE" ]; then
    info "读取部署目标默认值：$TARGET_FILE"
    while IFS= read -r line || [ -n "$line" ]; do
        line="$(printf '%s' "$line" | tr -d '\r')"
        case "$line" in ''|\#*) continue ;; esac
        key="${line%%=*}"
        value="${line#*=}"
        key="$(printf '%s' "$key" | tr -d '[:space:]')"
        value="$(printf '%s' "$value" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
        case " $TARGET_KEYS " in
            *" $key "*) ;;
            *) warn "  忽略未识别的键：$key（可用：$TARGET_KEYS）"; continue ;;
        esac
        # 环境变量优先：仅在未设置时采用文件里的值
        [ -n "${!key:-}" ] || export "$key=$value"
    done < "$TARGET_FILE"
fi

SERVER_IP="${SERVER_IP:-}"
SERVER_USER="${SERVER_USER:-root}"
SSH_PORT="${SSH_PORT:-22}"
PROJECT_DIR="${PROJECT_DIR:-/root/arboris-novel}"
REPO_URL="${REPO_URL:-}"
GIT_BRANCH="${GIT_BRANCH:-main}"

if [ -z "$SERVER_IP" ]; then
    die "未指定目标服务器。请设置 SERVER_IP 环境变量，或创建 $TARGET_FILE（格式见本脚本头部注释）"
fi

echo "========================================="
echo " Arboris-Novel 一键远程部署"
echo "========================================="
echo ""
echo "  服务器：    $SERVER_USER@$SERVER_IP:$SSH_PORT"
echo "  项目目录：  $PROJECT_DIR"
echo "  分支：      $GIT_BRANCH"
echo "  仓库：      ${REPO_URL:-（已存在则不需要）}"
echo "  compose：   ${COMPOSE_FILE:-docker-compose.yml}"
echo "  先跑迁移：  ${RUN_MIGRATIONS:-0}"
echo ""

if [ "${ASSUME_YES:-0}" != "1" ]; then
    [ -t 0 ] || die "非交互环境请显式设置 ASSUME_YES=1"
    echo -e "${YELLOW}确认部署到以上服务器吗？(yes/no)${NC}"
    read -r response
    [ "$response" = "yes" ] || die "已取消"
fi

# ---- SSH 连通性 ---------------------------------------------------------------
info "测试 SSH 连接…"
if ssh -p "$SSH_PORT" -o ConnectTimeout=8 -o BatchMode=yes "$SERVER_USER@$SERVER_IP" 'echo ok' >/dev/null 2>&1; then
    ok "SSH 连接正常"
else
    die "SSH 连接失败。请检查：① 地址/端口 ② 免密密钥 ③ 服务器在线 ④ 安全组放行"
fi

# ---- 远程执行 -----------------------------------------------------------------
# heredoc 用引号（'ENDSSH'）以免本机提前展开；需要的值通过命令行前缀显式传进去。
# 老版本把 $ENV_FILE 写在引号 heredoc 里，远端展开为空导致 [ ! -f "" ] 恒真、每次必退——这里一并修掉。
info "开始远程部署…"
echo ""
ssh -p "$SSH_PORT" "$SERVER_USER@$SERVER_IP" \
    "PROJECT_DIR='$PROJECT_DIR' \
     REPO_URL='$REPO_URL' \
     GIT_BRANCH='$GIT_BRANCH' \
     COMPOSE_FILE='${COMPOSE_FILE:-}' \
     RUN_MIGRATIONS='${RUN_MIGRATIONS:-0}' \
     NO_CACHE='${NO_CACHE:-0}' \
     bash -s" <<'ENDSSH'
set -euo pipefail

echo "========================================="
echo " 远程部署流程（$(hostname)）"
echo "========================================="

# 1. 代码
if [ ! -d "$PROJECT_DIR/.git" ]; then
    [ -n "$REPO_URL" ] || { echo "✗ $PROJECT_DIR 不是 git 仓库，且未提供 REPO_URL 供首次克隆" >&2; exit 1; }
    echo "→ 首次克隆 $REPO_URL → $PROJECT_DIR"
    mkdir -p "$(dirname "$PROJECT_DIR")"
    git clone "$REPO_URL" "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"
echo "→ 拉取 origin/$GIT_BRANCH"
git fetch origin "$GIT_BRANCH"
git reset --hard "origin/$GIT_BRANCH"
echo "  当前提交：$(git log --oneline -1)"

# 2. 环境配置
if [ ! -f "$PROJECT_DIR/deploy/.env" ] && [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "✗ 未找到 $PROJECT_DIR/deploy/.env，请先在服务器上准备好环境变量" >&2
    exit 1
fi
echo "→ 环境配置已就绪"

# 3. Docker
if ! command -v docker >/dev/null 2>&1; then
    echo "→ 安装 Docker…"
    curl -fsSL https://get.docker.com | bash
    systemctl enable --now docker
fi
if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    echo "→ 安装 docker compose 插件…"
    apt-get update -y && apt-get install -y docker-compose-plugin
fi

# 4. 构建并起容器（迁移与缓存策略由 deploy_docker.sh 按环境变量处理）
# COMPOSE_FILE 为空时不要导出：docker compose 见到空值会当成"没提供配置文件"而报错。
[ -n "$COMPOSE_FILE" ] && export COMPOSE_FILE || unset COMPOSE_FILE
export RUN_MIGRATIONS NO_CACHE
bash deploy/scripts/deploy_docker.sh

echo ""
echo "========================================="
echo " 远程部署完成"
echo "========================================="
ENDSSH

echo ""
echo "========================================="
ok "一键部署完成"
echo "========================================="
echo ""
echo "  访问：    http://$SERVER_IP"
echo "  远程日志：ssh -p $SSH_PORT $SERVER_USER@$SERVER_IP 'cd $PROJECT_DIR/deploy && docker compose logs -f app'"
echo ""
