#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-gen2.sh .arb-deploy2.sh
cat > /tmp/arb-msg11.txt <<'MSG'
feat(progress): 接管别人发起的生成时不装作知道进度

刷新页面/换设备后进度视图会「接管」一个已在跑的生成，此时本页没有任何进度来源。
之前它照旧画一个 5% 的静止进度条、写「等待开始...」、按打开本页的时间推算「预计剩余
X 分钟」——三样都是编的。现在这种情况显示不定量进度条、说明「这一章在你打开本页前
就开始了」、时间写「已等待」而不是「已用时」，剩余时间改成「完成后自动出现」。

移动端实测顺带确认：390px 下进度卡片完整可读（302px 宽），无横向溢出。
MSG
git add -A
git commit -F /tmp/arb-msg11.txt
rm -f /tmp/arb-msg11.txt
git push origin main 2>&1 | tail -1
git log --oneline -1
