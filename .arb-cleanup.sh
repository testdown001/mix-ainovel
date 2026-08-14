#!/usr/bin/env bash
cd /home/aikev/code/arboris-novel
git rm -q --cached .arb-commit.sh 2>/dev/null || true
rm -f .arb-commit.sh
git add -A
git commit -q -m "chore: 清理临时脚本" || true
git push -q origin main
git log --oneline -1
