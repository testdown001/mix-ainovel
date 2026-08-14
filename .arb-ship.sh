#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
cat > /tmp/arb-msg10.txt <<'MSG'
fix(mobile): 移动端实测三处修复 + 生成中章节不再被缓存报成「未生成」

390px 视口实测详情页 / 写作台 / 生成进度三个只读场景，发现的都不是「挤了点」，
而是直接够不着：

1. 写作台头部的按钮组在 390px 下被裁掉。卡片是 overflow-x:hidden，右侧「设定典」
   「重新生成」延伸到 x=551，既看不见也滚不到——手机上没法重新生成任何章节。
   头部与按钮组加 flex-wrap，窄屏换行。

2. 详情页的主操作「开始创作」挂在横向滚动的标签条末尾（ml-auto），390px 下位于
   x=840，用户得把标签条一路划到底才能看见整个页面最主要的按钮。把它移出滚动容器，
   标签条自己滚，按钮常驻可见。

3. 项目详情接口把正在生成的章节报成「未生成」。GET /api/novels/{id} 走 30 分钟 TTL
   的序列化缓存，而生成路径直接改 ORM 对象、不经过 NovelService 的写路径，缓存不会
   失效。线上实测：第 18 章 SSE 正在吐字、单章接口返回 generating，项目接口却一直是
   not_generated。后果有两层——上一批做的「刷新后提示后台仍在生成」永远不会触发，
   而且前端据此认为该章没在跑，用户可以对同一章再点一次生成（重复跑、重复扣费）。
   三个直接写章节状态的地方（编排器置 generating、worker 置 generating、
   同步路径置 failed）补上缓存失效，失败只记日志不影响生成。
MSG
git add -A
git commit -F /tmp/arb-msg10.txt
rm -f /tmp/arb-msg10.txt
git push origin main 2>&1 | tail -1
git log --oneline -1
