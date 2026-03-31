#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
{
  echo "=== go build ./... ==="
  if go build ./... 2>&1; then
    echo "BUILD_OK"
  else
    echo "BUILD_FAIL exit=$?"
    exit 1
  fi
  echo "=== go vet ./... ==="
  go vet ./... 2>&1 && echo "VET_OK" || echo "VET_FAIL exit=$?"
  echo "=== go file count ==="
  find . -name '*.go' -not -path './vendor/*' | wc -l
} > _build_report.out 2>&1
echo done >> _build_report.out
