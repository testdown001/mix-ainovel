#!/usr/bin/env bash
# Source before manual Compose build/up. Never source .release.env directly.
#   source deploy/scripts/prepare_release_metadata.sh build
#   (cd deploy && docker compose build)
#   source deploy/scripts/prepare_release_metadata.sh deploy
#   (cd deploy && docker compose up -d --no-build)
# Restart/recreate reads the existing .env event; do not run deploy again.
# `load` explicitly restores a snapshot. Image rollback: deploy, no build.

prepare_release_metadata() {
    local mode="${1:-build}" script_dir root exports
    local args=()
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || return
    root="$(cd "$script_dir/../.." && pwd)" || return
    command -v python3 >/dev/null 2>&1 || {
        echo "发布元数据需要 python3，请先安装。" >&2
        return 1
    }
    [ -z "${ENV_FILE:-}" ] || args+=(--env-file "$ENV_FILE")
    exports="$(python3 "$script_dir/release_metadata.py" "$mode" --root "$root" "${args[@]}")" || return
    # Only the trusted helper emits shell-quoted exports of the allowlisted
    # metadata keys. The persistent dotenv file is never executed as shell code.
    eval "$exports"
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    prepare_release_metadata "${1:-build}"
else
    echo "请使用 source $0 [build|deploy|load]，使元数据进入当前 Compose shell。" >&2
    exit 1
fi
