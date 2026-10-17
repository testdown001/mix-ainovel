# 管理后台发布版本信息

管理员的系统统计页展示运行中应用的 Git 提交、分支、提交时间、构建时间，以及实际发布事件的时间和标识。该接口仅管理员可访问，不需要数据库迁移。

## 数据来源和时间含义

- **Git 提交时间**：提交本身的时间，不是发布时间。
- **构建时间**：部署脚本采集本次构建身份时的 UTC 时间。
- **部署时间**：构建完成后、执行 Compose `up` 前生成的一次 UTC 发布事件。它不是容器启动时间，也不表示健康检查完成时间。
- **镜像身份优先**：构建把非秘密元数据写入镜像 `/app/release-info.json`；宿主后来执行 `git pull` 不会改变正在运行的镜像版本。
- **构建与部署绑定**：镜像 `build_id` 必须匹配 `APP_DEPLOYED_BUILD_ID`，才展示该镜像的部署时间。手工换镜像但没登记事件时显示未知，不沿用旧发布时间。
- 缺失信息保持未知。旧镜像、旧归档不通过构建时间、进程启动时间或文件修改时间补猜发布时间。

## 自动部署

`deploy_docker.sh`、`server_deploy.sh`、`quick_deploy.sh` 和 `oneclick_prod_https.sh` 已接入同一元数据采集流程。主机需要 Python 3；引导脚本会在缺失时安装。

1. 构建前只读采集完整 SHA、分支、提交时间、工作区修改状态，生成唯一 `APP_BUILD_ID` 和构建时间。
2. Compose build args 将这些值传入 Dockerfile，使用 Python JSON 序列化，不拼接分支名到 shell 命令。
3. 构建完成后，生成一次所有应用副本共享的部署时间与部署 ID，再执行 `up --no-build`。
4. 非秘密快照保存为已忽略的 `deploy/.release.env`。部署事件的 **三个键** 同时逐行更新既有 Compose `.env`：`APP_DEPLOYED_AT`、`APP_DEPLOYMENT_ID`、`APP_DEPLOYED_BUILD_ID`。其他内容字节、文件权限及属主保持不变，不复制密钥到发布快照或镜像。

`ENV_FILE` 可指定既有配置；否则使用 `deploy/.env`，不存在时回落到根 `.env`。根配置场景下，后续直接运行 Compose 仍需显式 `--env-file ../.env`，与现有配置选择保持一致。

普通 `docker compose restart`、容器自动重启或无新构建的 recreate 保留原部署事件，不重新采集 Git。数据库恢复脚本 `rollback.sh` 不是代码发布，也不更新该事件。

## 手工 Compose 发布

在仓库根目录执行；生产栈先按原流程设置 `COMPOSE_FILE=docker-compose.prod.yml` 或现有 override 组合：

```bash
source deploy/scripts/prepare_release_metadata.sh build
(cd deploy && docker compose build)
source deploy/scripts/prepare_release_metadata.sh deploy
(cd deploy && docker compose up -d --no-build)
```

必须使用 `source`，使本次构建身份进入当前 shell；不要直接 source `.release.env`，它是数据文件。独立执行 `docker build` 或 Compose build 而不提供参数仍可构建，只是镜像版本信息显示未知。

部署后重启无需再次运行 `deploy`。换新代码重新构建时必须重新执行 `build`，不能只加载历史快照冒充新构建。

## 回滚旧镜像

先按既有运维流程选定并配置真正要启动的旧镜像；读取该镜像 `/app/release-info.json` 的 `build_id`，设置为当前 shell 的 `APP_BUILD_ID`，然后 source helper 的 `deploy` 模式并执行 `up --no-build`。`deploy` 模式不读取宿主 HEAD、不重构建，也不改旧镜像的 Git 身份。

若旧镜像没有 `build_id`，或无法确认实际镜像身份，留空 `APP_BUILD_ID`；后台部署时间保持未知，不编造旧镜像的发布时间。不要运行 `build` 模式后再把宿主新代码的身份登记给旧镜像。

## 离线校验

```bash
python3 -m unittest discover -s deploy/tests -v
bash -n deploy/scripts/{_common,deploy_docker,server_deploy,quick_deploy,rollback,oneclick_prod_https,prepare_release_metadata}.sh
```

测试使用临时 Git 仓库和临时环境文件，不连接 Docker daemon、远程服务器、数据库或模型。
