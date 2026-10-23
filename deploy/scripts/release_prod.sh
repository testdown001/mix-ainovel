#!/usr/bin/env bash
# =============================================================================
# 生产栈（docker-compose.prod.yml，3×app 副本）的标准发布脚本。在服务器仓库根目录执行：
#
#     bash deploy/scripts/release_prod.sh [发布名]
#
# 做的事（和 2026-09/10 以来服务器上手工敲的流程一样，只是把漏掉的一步补回来）：
#   1. git fetch + ff-only 合并 origin/main，并把本地 main 推回 GitHub
#   2. 采集发布元数据（完整 SHA / 分支 / 提交时间 / 构建时间 / 构建 ID）——
#      这一步漏掉的话，镜像里的 /app/release-info.json 全是 null，
#      后台「系统版本与部署」只会显示「未知」（2026-10-23 连续五次手工发布都这样）
#   3. 只构建 app 镜像，日志落到 backups/release-<名>-<UTC 时间>/
#   4. 登记部署事件（写入 deploy/.env 的 APP_DEPLOYED_*），只重建 app 副本（--no-deps）
#   5. 跑 Alembic 迁移，校验三副本 healthy、无 "Application startup failed"、/api/health 200
#
# 可选环境变量：
#   SKIP_GIT=1          不 fetch/merge/push（已手工同步好代码时）
#   RUN_MIGRATIONS=0    跳过迁移与结构校验
#   NO_CACHE=1          构建不复用缓存
#   WAIT_TIMEOUT=180    等待副本 healthy 的秒数
#
# gateway / nginx 有改动时，另外手工：docker compose … up -d --no-deps gateway / nginx reload。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/_common.sh
. "$SCRIPT_DIR/_common.sh"

export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
RELEASE_NAME="${1:-release}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="$PROJECT_ROOT/backups/release-${RELEASE_NAME}-${STAMP}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-180}"

[ -f "$DEPLOY_DIR/$COMPOSE_FILE" ] || die "未找到 $DEPLOY_DIR/$COMPOSE_FILE"
require_docker
load_env
mkdir -p "$RELEASE_DIR"

echo "========================================="
echo " Arboris-Novel 生产发布：$RELEASE_NAME"
echo " compose: $(compose_desc)   日志目录: $RELEASE_DIR"
echo "========================================="

# ---- 1. 代码 -----------------------------------------------------------------
if [ "${SKIP_GIT:-0}" != "1" ]; then
    info "同步代码（fetch + ff-only merge origin/main + push）…"
    git -C "$PROJECT_ROOT" fetch -q origin main
    git -C "$PROJECT_ROOT" merge -q --ff-only origin/main
    git -C "$PROJECT_ROOT" push -q origin main || warn "推回 GitHub 失败（不影响发布，稍后手工 push）"
fi
ok "HEAD = $(git -C "$PROJECT_ROOT" rev-parse HEAD)"

# ---- 2. 发布元数据 → 3. 构建 ---------------------------------------------------
# 必须 source：把 APP_GIT_* / APP_BUILD_ID 导出到当前 shell，compose 的 build.args 才能插值。
. "$SCRIPT_DIR/prepare_release_metadata.sh" build
short_commit="${APP_GIT_COMMIT:-}"
ok "构建身份：commit=${short_commit:0:12} branch=${APP_GIT_BRANCH:-?} dirty=${APP_GIT_DIRTY:-?} build_id=${APP_BUILD_ID:-?}"

info "构建 app 镜像（日志：$RELEASE_DIR/build.log）…"
BUILD_ARGS=()
[ "${NO_CACHE:-0}" != "1" ] || BUILD_ARGS+=(--no-cache)
if ! dc --env-file "$ENV_FILE" build ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"} "$APP_SERVICE" > "$RELEASE_DIR/build.log" 2>&1; then
    tail -40 "$RELEASE_DIR/build.log" >&2
    die "构建失败，完整日志见 $RELEASE_DIR/build.log"
fi
ok "BUILD_SUCCESS"

# ---- 4. 部署事件 → 重建 app 副本 ---------------------------------------------
# deploy 模式把 APP_DEPLOYED_AT / APP_DEPLOYMENT_ID / APP_DEPLOYED_BUILD_ID 逐行写进 deploy/.env，
# 之后普通 restart / recreate 都沿用这一次事件，不会再采集。
. "$SCRIPT_DIR/prepare_release_metadata.sh" deploy
ok "部署事件：${APP_DEPLOYMENT_ID:-?} @ ${APP_DEPLOYED_AT:-?}"

info "滚动重建 app 副本（--no-deps --force-recreate --wait，日志：$RELEASE_DIR/deploy.log）…"
if ! dc --env-file "$ENV_FILE" up -d --no-build --no-deps --force-recreate \
        --wait --wait-timeout "$WAIT_TIMEOUT" "$APP_SERVICE" > "$RELEASE_DIR/deploy.log" 2>&1; then
    tail -40 "$RELEASE_DIR/deploy.log" >&2
    die "副本未能在 ${WAIT_TIMEOUT}s 内 healthy，见 $RELEASE_DIR/deploy.log 与 docker logs"
fi
ok "DEPLOY_SUCCESS"

# ---- 5. 迁移 + 校验 ----------------------------------------------------------
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    info "执行数据库迁移…"
    SKIP_BACKUP="${SKIP_BACKUP:-1}" bash "$SCRIPT_DIR/run_migrations.sh"
else
    warn "RUN_MIGRATIONS=0：跳过迁移"
fi

sleep 3
FAILED=0
for name in $(docker ps --format '{{.Names}}' | grep -E "^deploy-${APP_SERVICE}-[0-9]+$" | sort); do
    health="$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo unknown)"
    boots="$(docker logs "$name" --since 10m 2>&1 | grep -c 'Application startup failed' || true)"
    echo "  $name  $health  startup_failed=$boots"
    { [ "$health" = "healthy" ] && [ "$boots" = "0" ]; } || FAILED=1
done
codes=""
for _ in 1 2 3; do codes="$codes $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/api/health)"; done
echo "  /api/health:$codes"
case "$codes" in *" 200 200 200"*) ;; *) FAILED=1 ;; esac
[ "$FAILED" = 0 ] || die "校验未通过，请看上面的副本状态"

echo ""
ok "发布完成：$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)  部署 ID ${APP_DEPLOYMENT_ID:-?}"
echo "  后台「系统版本与部署」应显示本次提交、构建时间与部署时间。"
