#!/usr/bin/env bash
# =============================================================================
# Docker 部署脚本（单容器栈 deploy/docker-compose.yml）
#
# 用法：
#     bash deploy/scripts/deploy_docker.sh
#
#   可选环境变量：
#     NO_CACHE=1        强制不复用构建缓存（默认复用，快很多；依赖清单变了会自动失效）
#     RUN_MIGRATIONS=1  构建前先跑 Alembic 迁移（见 run_migrations.sh）
#     COMPOSE_FILE=...  换用其它 compose 文件（docker 原生变量，多文件用 : 分隔）
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/_common.sh
. "$SCRIPT_DIR/_common.sh"

echo "========================================="
echo " Arboris-Novel Docker 部署"
echo "========================================="

ENV_EXAMPLE_FILE="$DEPLOY_DIR/.env.example"

[ -f "$DEPLOY_DIR/docker-compose.yml" ] || die "未找到 $DEPLOY_DIR/docker-compose.yml"

# ---- .env ---------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ] && [ ! -f "$PROJECT_ROOT/.env" ]; then
    warn "未找到环境配置文件 $ENV_FILE"
    if [ -f "$ENV_EXAMPLE_FILE" ] && [ -t 0 ]; then
        echo "是否用示例配置创建？(y/n)"
        read -r response
        if [ "$response" = "y" ]; then
            cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
            ok "已创建 $ENV_FILE，请填写后重新运行"
        fi
    fi
    die "请先准备 $ENV_FILE（可参考 $ENV_EXAMPLE_FILE）"
fi

require_docker
load_env
ok "Docker 与 Compose 就绪（${DC[*]}）"

# SECRET_KEY / MYSQL_PASSWORD 在 compose 里是 ${VAR:?} 强制插值，缺了直接起不来。
require_env SECRET_KEY MYSQL_PASSWORD
# LLM Key 不是硬性前置：运行时 LLM 配置以 SystemConfig(后台「接口管理」)为准，env 只是首启种子。
if [ -z "${OPENAI_API_KEY:-}" ]; then
    warn "未设置 OPENAI_API_KEY —— 服务能起，但生成章节前需在后台「接口管理」填真实 Key"
fi

# ---- 数据库与 profile ---------------------------------------------------------
# 把 profile 并进 compose 命令数组，后续统一用 dcp 调用（避免各处拼空数组）。
DB_PROVIDER="${DB_PROVIDER:-sqlite}"
DCP=("${DC[@]}")
echo ""
info "数据库：$DB_PROVIDER"
if [ "$DB_PROVIDER" = "mysql" ]; then
    DCP+=(--profile mysql)
    info "  主机 ${MYSQL_HOST:-db}:${MYSQL_PORT:-3306} 库 ${MYSQL_DATABASE:-arboris}"
else
    info "  使用 SQLite（开发模式）"
fi

dcp() { ( cd "$DEPLOY_DIR" && "${DCP[@]}" "$@" ); }

# ---- 迁移（显式 opt-in；应用启动时的 init_db() 也会自愈结构）------------------
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo ""
    info "执行数据库迁移…"
    bash "$SCRIPT_DIR/run_migrations.sh"
fi

# ---- 停旧 / 构建 / 起新 -------------------------------------------------------
echo ""
info "停止旧容器…"
dcp down || true

echo ""
if [ "${NO_CACHE:-0}" = "1" ]; then
    info "构建镜像（--no-cache）…"
    dcp build --no-cache
else
    info "构建镜像（复用缓存；requirements/package-lock 变更会自动失效）…"
    dcp build
fi

echo ""
info "启动容器…"
dcp up -d

echo ""
info "容器状态："
dcp ps

# ---- 健康检查 -----------------------------------------------------------------
echo ""
info "等待服务就绪（最多约 2 分钟）…"
HEALTHY=false
for _ in $(seq 1 60); do
    # </dev/null 必须有：本脚本会被 quick_deploy.sh 经 `ssh … bash -s` 管道执行，
    # docker exec 接管 stdin 会把远端脚本剩余内容吞掉（见 _common.sh 说明）。
    if dcp exec -T "$APP_SERVICE" curl -fs http://127.0.0.1:8000/api/health </dev/null >/dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 2
done

if [ "$HEALTHY" != true ]; then
    warn "健康检查未通过，最近日志："
    dcp logs --tail=50 "$APP_SERVICE" || true
    die "部署失败。常见原因：端口被占用 / 数据库连接配置错误 / 依赖安装失败"
fi
ok "健康检查通过"

# ---- 完成 ---------------------------------------------------------------------
echo ""
echo "========================================="
ok "部署成功"
echo "========================================="
echo ""
echo "  前端：    http://localhost:${APP_PORT:-80}"
echo "  健康检查：http://localhost:${APP_PORT:-80}/api/health"
echo "  管理员：  ${ADMIN_DEFAULT_USERNAME:-admin}（密码见 $ENV_FILE 的 ADMIN_DEFAULT_PASSWORD）"
echo ""
echo "  常用命令（在 $DEPLOY_DIR 下）："
echo "    日志：${DC[*]} logs -f $APP_SERVICE"
echo "    重启：${DC[*]} restart"
echo "    停止：${DC[*]} down"
echo ""
