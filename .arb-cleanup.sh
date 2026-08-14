#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-commit.sh .arb-check.sh .arb-verify.sh .arb-deploy.sh
git add -A
git commit -q -m "chore: 移除部署验证用的临时脚本"
git push -q origin main
git status --short
git log --oneline -1
